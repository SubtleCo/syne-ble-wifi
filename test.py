# import subprocess
with open('/var/lib/dbus/machine-id', 'r') as file :
  filedata = file.read()
print(filedata)