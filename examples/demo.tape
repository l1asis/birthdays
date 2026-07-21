# Output settings
Output examples/demo.gif
Set FontSize 15
Set Width 915
Set Height 600
Set Padding 30
Set Theme "Dracula"
Set WindowBar Colorful

# Hidden setup
Hide
Type "export DEBIAN_FRONTEND=noninteractive"
Enter

# Install base requirements
# DEBUG: "> examples/setup.log 2>&1"
Type "apt update && apt install -y python3 python3-pip python3-venv"
Enter
Sleep 60s

# Download the Charm's gum
Type "apt update && apt -y install gum"
Enter
Sleep 45s

# Install the birthdays package
Type "pip3 install . --break-system-packages"
Enter
Sleep 15s

Type "clear"
Enter
Show

# Show the fake contacts data
Type "gum pager < examples/contacts.vcf"
Sleep 500ms
Enter
Sleep 500ms

# Scroll down to view more contacts
Down@40ms 35
Sleep 500ms

# Exit the pager so we can run commands again
Type "q"
Sleep 500ms

# Run the import command
Type "birthdays import examples/contacts.vcf"
Sleep 500ms
Enter
Sleep 1s

# Show the list view
Type "birthdays list --sort upcoming"
Sleep 500ms
Enter
Sleep 6s