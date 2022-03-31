"""
https://docs.google.com/document/d/147exjQT8h3cr-aUrZURNfwWVgqrVaJNRb8Y_hKnKeNA/edit#

This program downloads a list of the user's courses using a key given in an .env file, removes courses
from before a relevant start time, downloads the assignments from each course, then removes any manually
blacklisted assignments and assignments due before a specified date before sorting the remaining ones.
Currently, the only way to single out an assignment to be ignored is by adding its id to the list saved in
the first line of the 'canvis.dat' file automatically created in the directory that this script is run.
Assignments may also be nicknamed by the user. Currently, nicknames must also be manually added to the
dictionary in the second line of the data file in the format {assignment id: "nickname"}.
Though the gui appears correctly, it is unfinished. Only the due date cutoff selection at the top and
redownload/refilter buttons at the bottom are functional.
"""

# Imports
import dotenv                 # to import environment variables from another file
import os                     # to use system stuff
import ast                    # to parse list and dictionary data from strings (json doesn't accept numeric keys)
import time                   # to record the time the program takes to do stuff
import datetime as dt         # to record and compare time
import webbrowser as wb       # to open links in the user's browser
from tkinter import *         # to add an interactive gui
from tkinter import ttk       # modern tkinter widgets
from canvasapi import Canvas  # sandwich recipes
# Load env
print("<=== Starting ===>")
start_time = time.time()  # Record start time
dotenv.load_dotenv(dotenv.find_dotenv())  # Load environment variables

# Objects
TOKEN = os.environ.get('CANVAS_API_TOKEN')  # Token
BASEURL = 'https://nbprep.instructure.com'  # URL
signin = Canvas(BASEURL, TOKEN)             # Sign in
tk_root = Tk()                              # Create tkinter root
# Make sure data file exists
dataFile = open("canvis.dat", "a")
dataFile.close()

# -Parameters
# Automatically obtained
local_tz = dt.datetime.now().astimezone().tzinfo
# Read from file
course_lower_cutoff = dt.datetime(2021, 7, 15, tzinfo=local_tz)     # The earliest date a course can start to be included *temporarily hardcoded
assignment_lower_cutoff = dt.datetime(2022, 2, 9, tzinfo=local_tz)  # The earliest date an assignment can start to be included *temporarily hardcoded
ignored_assignments = []                                            # List of ids of assignments specifically selected by user to be ignored
assignment_nnames = {}                                              # Assignment nicknames

# -Global Variables
# Assignment data
inc_courses = {}        # Dict of courses included, keyed with course id
pd_courses = []         # List of courses outdated by given time frame
inc_assignments = []    # 2D list of assignments included ([] = date, [][] = assignment)
pd_assignments = []     # List of assignments outdated by given time frame
exc_assignments = []    # List of assignments excluded by filters

# -Data
print("Signing in...")
# noinspection PyTypeChecker
user = signin.get_user('self')  # Sign in as user


# Sort a 1D list of assignments into a 2D list of assignments sorted by date
def sort_into_dates(asmts):
    list_final = []     # The final list containing every assignment sorted

    for asmt in asmts:  # Sort every assignment
        assignment_time = asmt.due_at_date.astimezone().date()  # Get assignment due time

        # Check for fitting date
        for date in list_final:                     # Check every list in included assignments
            if date[0] == assignment_time:              # If the assignment's date matches up with the list
                if asmt not in date[1:]:                    # If the assignment isn't already in the list
                    date.append(asmt)                           # Add it to the list
                break                                       # Stop checking lists

        else:                                       # If it's done checking but a matching date wasn't found
            list_final.append([assignment_time, asmt])  # Append a new list for the new date with assignment

    return list_final   # Return filled out list


# Download and date assignments
def refresh_assignments(print_on_completion=False):
    # Declare globals (why does python do this it's already bad practice shadowing globals)
    global inc_courses
    global pd_courses
    global inc_assignments
    global pd_assignments
    # Refresh assignments
    print("Refreshing assignments:")

    # Get data
    print("Getting courses...")
    courses = user.get_courses()  # Get user courses

    # Check if start time in within timeframe for each course
    print("Filtering courses")
    starting_courses = [course for course in courses if course.start_at_date is not None]  # List of courses with start dates

    # Sort course into included and past-due lists 
    inc_courses = {course.id: course for course in starting_courses if course.start_at_date >= course_lower_cutoff}  # 1D dict of assignments on or past cutoff date
    pd_courses = [course for course in starting_courses if course.start_at_date < course_lower_cutoff]               # List of assignments before cutoff date

    # Print included courses
    print("Included courses:")
    for c_id, course in inc_courses.items():
        print(course)

    # Print excluded courses
    '''print("Excluded courses:")
    for course in pd_courses:
        print(course)'''
    print()

    inc_as1d = []
    # Check if due time in within timeframe for each assignment
    for course_id, course in inc_courses.items():
        # Get and filter assignments by date
        print("Getting assignments... (" + str(course) + ")")
        assignments = course.get_assignments()                # Get assignments

        print("Filtering out early assignments by due date")
        due_assignments = [asmt for asmt in assignments if hasattr(asmt, "due_at_date")]                    # List of assignments with due dates
        # Sort assignments into included and past-due lists
        inc_as1d += [asmt for asmt in due_assignments if asmt.due_at_date >= assignment_lower_cutoff]       # 1D list of assignments on or past cutoff date
        pd_assignments = [asmt for asmt in due_assignments if asmt.due_at_date < assignment_lower_cutoff]   # List of assignments before cutoff date
# SPLIT UP THE FILTERING AND SORTING OF NEW ASSIGNMENTS INTO ITS OWN FUNCTION SO THAT IT CAN BE CALLED AFTER REFRESH_DATA()
    # Sort included assignments into dates
    print("Sorting assignments by dates")
    inc_as1d.sort(key=lambda asmt: asmt.due_at_date)  # Sort the assignments in the 1D list
    print("Sorting assignments into dates")
    inc_assignments = sort_into_dates(inc_as1d)       # Sort the 1D list of included assignments into the 2D date one

    print("---- Finished data download and sort ----")
    refresh_data(True, True)
    if print_on_completion:
        print_assignments()


# Refresh assignments by filters
def refresh_data(remove_unused=True, read_file=True):  # remove_unused should be true whenever refreshing for the current date, also add a little notice that assignments won't be ignored if due before present date
    # Declare globals
    global ignored_assignments
    global inc_assignments
    global exc_assignments
    global assignment_nnames
    global dataFile
    global listbox_dates
    global list_dates
    # Refresh filters and other file data
    print("Refreshing data:")

    # If it should overwrite current data with data from file
    if read_file:
        # Read file data
        print("Reading data file...")
        dataFile = open("canvis.dat", "r")          # Open data file for reading
        data_lines = dataFile.read().splitlines()   # Read data file and split into list (without newline symbols)
        dataFile.close()                            # Close data file
        # Make sure file has enough lines
        while len(data_lines) < 3:  # While data has too few lines (CURRENTLY EXPECTING: 3 LINES)
            data_lines.append("")   # Append data list with empty string

        # Define code that parses the data from a line
        def parseline(line, empty_of_type, data_name):
            try:                                                 # Try to parse data in line (will fail if file data is invalid, or raise an error if wrong type)
                read_data = ast.literal_eval(data_lines[line])   # Attempt to parse and record data from line (may fail if input is invalid)
                if type(read_data) != type(empty_of_type):       # Make sure data is the right type
                    raise TypeError(data_name, "must be stored in a(n)", str(type(empty_of_type)), "but data is", str(type(read_data)))  # Raise an error if not

            except SyntaxError as err:                              # If the data is invalid
                print("Failed to parse", data_name, "from line", str(line) + ". Defaulting to empty", str(type(empty_of_type)) + ".\nDetails:", err.msg)
                read_data = empty_of_type                               # Reset data to empty

            except TypeError:                                       # If the data is wrong type
                print(data_name, "not stored as a", str(type(empty_of_type)) + ". Defaulting to empty", str(type(empty_of_type)) + ".")
                read_data = empty_of_type                               # Reset data to empty

            return read_data  # Return data

        # Get ignored assignment ids from file (list at line 0)
        print("Reading ignored assignments")
        ignored_assignments = parseline(0, [], "ignored assignment ids")  # Record list of ignored assignment ids

        # Get assignment nicknames from file (dict at line 1)
        print("Getting assignment nicknames")
        assignment_nnames = parseline(1, {}, "assignment nicknames")

        # Get date settings from file (dict at line 1)
        print("Getting assignment nicknames")
        assignment_nnames = parseline(1, {}, "assignment nicknames")

    # -- Filter ignored assignments
    # Filter assignments in/out using ignored assignment list
    print("Removing ignored assignments")

    # Collect all assignments, sort into included and excluded by ids using ignored
    all_assignments = [asmt for date in inc_assignments for asmt in date[1:]] + exc_assignments  # Get all assignments
    if show_all.get() or len(ignored_assignments) == 0:
        # If to show all assignments/not removing any assignments
        inc_assignments = sort_into_dates(all_assignments)  # Sort the 1D list of all assignments into the 2D date one
    else:
        # If to filter assignments
        inc_as1d = [asmt for asmt in all_assignments if asmt.id not in ignored_assignments]     # Get included assignments (id not on ignore list)
        exc_assignments = [asmt for asmt in all_assignments if asmt.id in ignored_assignments]  # Get excluded assignments (id is on ignore list)
        inc_assignments = sort_into_dates(inc_as1d)                                             # Sort the 1D list of included assignments into the 2D date one

        # Filter out unused ignored ids (if intended)
        if remove_unused:                                                                       # If unused ignored ids should be removed
            all_ids = [asmt.id for asmt in all_assignments]                                         # Get all assignment ids
            ignored_unused = [rem_id for rem_id in ignored_assignments if rem_id not in all_ids]    # Get all ignore ids not matching an assignment
            for rem_id in ignored_unused:                                                           # For every unused ignore id,
                ignored_assignments.remove(rem_id)                                                      # Remove it

    # Apply new entries to date listbox
    listbox_dates.delete(0, len(list_dates.get())-1)                      # Remove old entries
    entries = [date[0].strftime('%m/%d/%y') for date in inc_assignments]  # Create list of dates
    list_dates = StringVar(value=entries)                                 # Update list of dates
    for i, entry in enumerate(entries):                                   # Reinsert new dates into listbox
        listbox_dates.insert(i, entry)
    print("---- Finished data refresh ----")


def save_data():
    # Declare globals
    global dataFile
    print("Saving file data:")

    # Update data
    data_lines = (str(ignored_assignments), str(assignment_nnames))  # The lines of data to go in the file, in a single string

    print("Rewriting to file")
    # Write new data to file
    dataFile = open("canvis.dat", "w")  # Open data file for overwriting
    dataFile.write("\n".join(data_lines))  # Write new data to file as a string
    dataFile.close()  # Close data file
    print("---- Finished filedata save ----")


def print_assignments():  # Print included assignments
    nname_keys = assignment_nnames.keys()
    print("\nAssignments after date " + str(assignment_lower_cutoff) + ":")
    for date in inc_assignments:  # Print something for every date
        print("\nAssignments on date: " + date[0].isoformat())
        for asmt in date[1:]:
            if asmt.id in nname_keys:
                print("ASSIGNMENT -", assignment_nnames[asmt.id], "(nickname) - FROM COURSE -", str(inc_courses[asmt.course_id]), "- DUE AT -", asmt.due_at_date.astimezone().strftime("%m/%d/%Y, %H:%M:%S"))
            else:
                print("ASSIGNMENT -", str(asmt), "- FROM COURSE -", str(inc_courses[asmt.course_id]), "- DUE AT -", asmt.due_at_date.astimezone().strftime("%m/%d/%Y, %H:%M:%S"))


# Main execution
# refresh_assignments(False)
# refresh_data(True, True)
# save_data()
# print_assignments()
print("<=== Finished processing! Time taken:", str(round((time.time() - start_time), 4)), "seconds ===>")


# Get a reliable reading of a listbox's cursor selection index
def curselval(listbox):
    if len(listbox.curselection()) != 0:
        # If cursor selection has a value, return it
        return listbox.curselection()[0]
    else:
        # If cursor selection doesn't have a value (nothing selected), return None
        return None


# START OF GUI CODE

# -- Functions --
# Add an assignment's id to the list of ignored assignments and refresh data without removing or loading ids
def ignore_assignment():
    ignored_assignments.append(inc_assignments[date_ind][asmt_ind + 1].id)
    refresh_data(False, False)


# Rename an assignment by adding text from the input box to the nickname dictionary under the assignment's id
def rename_assignment():
    global assignment_nnames

    assignment_nnames[inc_assignments[date_ind][asmt_ind + 1].id] = nickname
    refresh_data(False, False)


# Remove an assignment's nickname by removing the entry of the nickname dictionary under the assignment's id
def remove_assignment_nickname():
    assignment_nnames.pop(inc_assignments[date_ind][asmt_ind + 1].id)
    refresh_data(False, False)


# Update gui settings when the user switches cutoff config mode, then update
def update_config_mode():
    # Update label
    dconf_label.set(date_labels[auto_date.get()])

    # Update cutoff value
    if auto_date.get() == 0:
        # Cutoff mode
        asmt_lower_cutoff_input.set((dt.datetime.now() - dt.timedelta(days=2)).strftime('%m/%d/%y'))  # Set to 2 days before current date as default
    else:
        # Auto mode
        asmt_lower_cutoff_input.set('2')  # Set to trail 2 days behind as default
    # Update function will automatically trigger as part of the trace set earlier.


# Attempt to process the cutoff config input into the global assignment cutoff value. Do nothing if input is invalid.
def try_cutoff_update(var, index, mode):  # no params are used but python complains if they aren't there
    # Declare globals
    global assignment_lower_cutoff

    # Check mode
    if auto_date.get() == 0:
        # Cutoff mode
        try:
            # Try setting cutoff to time described in input, assuming resembles correct format
            assignment_lower_cutoff = dt.datetime.strptime(asmt_lower_cutoff_input.get(), "%m/%d/%y").replace(tzinfo=local_tz)
        except ValueError:  # Input is not formatted correctly
            pass
    else:
        # Auto mode
        try:
            # Try setting cutoff by subtracting number of days in input from current date, assuming input is int
            assignment_lower_cutoff = (dt.datetime.now() - dt.timedelta(days=int(asmt_lower_cutoff_input.get()))).replace(tzinfo=local_tz)
        except ValueError:  # Input is not int
            pass
# my hope is that this code is so horrendous that the python developers have no choice but to rework the datetime system
    print("New cutoff date:", assignment_lower_cutoff)


# Open the link of the selected assignment in the user's default browser
def open_selected_link():
    link = inc_assignments[date_ind][1:][asmt_ind].html_url
    wb.open_new_tab(link)


# Update selection indexes for changing date and set values of assignment display to the assignments of selected date
def update_asmt_list(pointless_tkinter_provided_argument_that_will_not_be_used):
    global listbox_assignments
    global list_assignments
    global date_ind
    global asmt_ind

    d = curselval(listbox_dates)
    if d is not None:  # Make sure that something was selected before making changes
        # Update selection indexes
        date_ind = d
        asmt_ind = 0

        # Apply new entries to assignment listbox
        listbox_assignments.delete(0, len(list_assignments.get())-1)  # Remove old entries
        entries = inc_assignments[date_ind][1:]                       # Get list of assignments
        list_assignments = StringVar(value=entries)                   # Update list of assignments
        for i, entry in enumerate(entries):                           # Reinsert new assignments into listbox
            listbox_assignments.insert(i, entry)


# Update selection index for selecting assignment
def update_asmt_sel_ind(pointless_tkinter_provided_argument_that_will_not_be_used):
    global asmt_ind

    d = curselval(listbox_assignments)
    if d is not None:  # Make sure that something was selected before making changes
        # Update selection index
        asmt_ind = d


# -- Variables --
date_ind = 0
asmt_ind = 0

# -- Set up window --
# Create window
tk_root.title("canvis")

# Create window frame
mainframe = ttk.Frame(tk_root, padding="4 6 12 12")

# Place it inside the main window
mainframe.grid(column=0, row=0, sticky=(N, W, E, S))

# Set root to automatically expand frame
tk_root.columnconfigure(0, weight=1)
tk_root.rowconfigure(0, weight=1)

# -- Set up widgets --
# ROW 1: Auto-date setting, date config label, date config, & 'Show all' checkbox
date_labels = ("Cutoff before date:", "Cutoff due days ago:")
dconf_label = StringVar(value=date_labels[1])
asmt_lower_cutoff_input = StringVar(value='2')

# Date config label
ttk.Label(mainframe, textvariable=dconf_label).grid(column=1, row=1, sticky=E)

# Date config
asmt_lower_cutoff_input.trace_add('write', try_cutoff_update)  # Call update when input changes
l_cutoff_entry = ttk.Entry(mainframe, width=9, textvariable=asmt_lower_cutoff_input)
l_cutoff_entry.grid(column=2, row=1, sticky=W)

# Auto-date setting
auto_date = IntVar(value=1)
auto_date_button = ttk.Checkbutton(mainframe, width=14, variable=auto_date, text="Auto-date", command=update_config_mode)
auto_date_button.grid(column=3, row=1)

# 'Show all' checkbox
show_all = BooleanVar()
showall_entry = ttk.Checkbutton(mainframe, width=14, variable=show_all, text="Show all")
showall_entry.grid(column=4, row=1, sticky=(E, W))

# ROW 2: Listbox labels, open link, & ignore button
# Listbox labels
ttk.Label(mainframe, text="Dates of assignments").grid(column=1, row=2, sticky=S)
ttk.Label(mainframe, text="Assignments of date").grid(column=2, row=2, sticky=S)

# Open link button
ttk.Button(mainframe, text="Open link", command=open_selected_link).grid(column=3, row=2, sticky=(E, W))

# Ignore button
ttk.Button(mainframe, text="Ignore", command=ignore_assignment).grid(column=4, row=2, sticky=(E, W))

# ROW 3: Set & remove nickname buttons
ttk.Button(mainframe, text="Set nickname", command=rename_assignment).grid(column=3, row=3, sticky=(E, W))
ttk.Button(mainframe, text="Remove nickname", command=remove_assignment_nickname).grid(column=4, row=3, sticky=(E, W))

# ROW 4: 'Nickname' entry box
nickname = StringVar()
nickname_entry = ttk.Entry(mainframe, width=14, textvariable=nickname)
nickname_entry.grid(column=3, columnspan=2, row=4, sticky=(W, E))

# ROW 5: Save button
ttk.Button(mainframe, text="Save changes", command=save_data).grid(column=4, row=5, sticky=(E, W))

# ROW 6: Download/filter data buttons
ttk.Button(mainframe, text="Redownload data", command=refresh_assignments).grid(column=4, row=6, sticky=(E, W))
ttk.Button(mainframe, text="Offline refresh", command=refresh_data).grid(column=3, row=6, sticky=(E, W))

# LISTBOXES
# Date listbox
list_dates = StringVar(value=[date[0].strftime('%m/%d/%y') for date in inc_assignments])
listbox_dates = Listbox(mainframe, listvariable=list_dates, height=10)
listbox_dates.grid(column=1, row=3, rowspan=4, sticky=(N, S, E, W))
listbox_dates.bind('<<ListboxSelect>>', update_asmt_list)

# Assignment listbox
list_assignments = StringVar(value=[])
listbox_assignments = Listbox(mainframe, listvariable=list_assignments, height=10)
listbox_assignments.grid(column=2, row=3, rowspan=4, sticky=(N, S, E, W))
listbox_assignments.bind('<<ListboxSelect>>', update_asmt_sel_ind)

# -- Finish up --
# Add padding to all children of the main frame
for child in mainframe.winfo_children():
    child.grid_configure(padx=5, pady=5)

# Finally, start the main loop
tk_root.mainloop()

# END OF GUI CODE
