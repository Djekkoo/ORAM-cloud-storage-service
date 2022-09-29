### Code to measure the file conversion system efficiency
### 
from monitor import Monitor
import random
import os
import shutil
import time
import math
from pprint import pprint
from settings import Settings
settings = Settings()


# ensure accidental activation of this script does not remove the regular testing directory
if settings.source_directory == './storage':
	print("Settings source directory is default \'./storage\', please change it to a directory that can be overwritten for testing")
	exit()

if settings.oram != None:
	print("ORAM method(settings.oram) has been set, please turn it to None to test the file conversion efficiency without the delay of client-server communication")
	exit()

# remove existing files(and directory) in source directory
if os.path.exists(settings.source_directory):
	shutil.rmtree(settings.source_directory)

# create specific testing directory for monitoring and file conversion script
os.mkdir(settings.source_directory)

# display testing configuration
print("Measure file conversion script with the following settings:")
print("Block size: " + str(settings.blockSize))
print("Use file hash: " + str(settings.file_hash))
print("Use block hash: " + str(settings.block_hash))
print("Use extends: " + str(settings.blocks_use_extends))


# get random content to write to files 1 blocksize in length
dummy_content = bytearray(random.getrandbits(8) for _ in range(settings.blockSize))


############# prepare basic files in testing directory
# files[name] = size
files = {}
# files of sizes 1 byte to 1KB 
for i in range(1, 1001):
	files['small_files/'+str(i)+'b.txt'] = i

# for i in range(1, 1001):
	# files['small_files_2/'+str(i)+'b.txt'] = i


# files of sizes 1KB - 1MB
for i in range(1, 1001):
	files['medium_files/'+str(i)+'kb.txt'] = 1000*i

# several files in range 1MB to 10MB
for i in range(1,11):
	files['large_files/'+str(i)+'mb.txt'] = 1000*1000*i

# several files in range 10mb to 100mb (10mb interval)
for i in range(10, 101, 10):
	files['large_files/'+str(i)+'mb.txt'] = 1000*1000*i


# write all files to source directory
for file in files:
	# dir exists
	if not os.path.exists(settings.source_directory + '/' + os.path.dirname(file)):
		os.mkdir(settings.source_directory + '/' + os.path.dirname(file))

	# write file of size files[file] 
	fp = open(settings.source_directory + '/'  + file, 'wb')
	tmp_size = files[file]
	while tmp_size > len(dummy_content):
		fp.write(dummy_content)
		tmp_size -= len(dummy_content)
		# change a random byte in dummy content to avoid repeated hash values per block
		dummy_content[random.randrange(0, len(dummy_content))] = random.getrandbits(8)

	fp.write(dummy_content[:tmp_size])
	# change dummy content to avoid repeats
	dummy_content = bytearray(random.getrandbits(8) for _ in range(settings.blockSize))


#################### create monitor and measure duration of the creation of the index file and blocks
tmp_time = time.time()

# create monitor
monitor = Monitor()

# measure elapsed time (time used to create index file and upload the content to the server)
# also collect the size of the index file, as well as the number of requests used to store all files on the server
index_file_elapsed_time = time.time() - tmp_time
index_file_size = os.path.getsize(settings.index_file)
content_used_blocks = monitor.index['general']['last_block_id'] - len(monitor.index['general']['deleted_blocks'])
total_files_size = sum(files.values())

print("\n========= Results for the setup of the basic file structure and indexation")
print("Time used to create index file and blocks: " + str(index_file_elapsed_time) + "s")
print("Size of the index file: " + str(index_file_size) + " bytes")
print("Number of blocks used to store all files: " + str(content_used_blocks) + " blocks")
print("Required server storage: " + str((content_used_blocks*settings.blockSize)/1000/1000) + "mb")
print("Total size of files: " + str(total_files_size/1000/1000) + "mb")
print("Efficiency of storage: " + str(round(total_files_size/(content_used_blocks*settings.blockSize)*100, 2)) + "%")


################ test additions
# copy all files in small_files directory to a new directory
add_new_files = {}


# files of sizes 1 byte to 1KB 
for i in range(1, 1001):
	add_new_files['small_files_added/'+str(i)+'b.txt'] = i

# files of sizes 1KB - 1MB
for i in range(1, 1001):
	add_new_files['medium_files_added/'+str(i)+'kb.txt'] = 1000*i

# files between 1MB and 100MB
add_new_files['large_1MB'] = 1*1000*1000
add_new_files['large_3MB'] = 3*1000*1000
add_new_files['large_5MB'] = 5*1000*1000
add_new_files['large_10MB'] = 10*1000*1000
add_new_files['large_25MB'] = 25*1000*1000
add_new_files['large_50MB'] = 50*1000*1000


# write all files to source directory
for file in add_new_files:
	# dir exists
	if not os.path.exists(settings.source_directory + '/' + os.path.dirname(file)):
		os.mkdir(settings.source_directory + '/' + os.path.dirname(file))

	# add file to files, and add size to total_files_size
	files[file] = add_new_files[file]

	# write file of size add_new_files[file] 
	fp = open(settings.source_directory + '/'  + file, 'wb')
	tmp_size = add_new_files[file]
	while tmp_size > len(dummy_content):
		fp.write(dummy_content)
		tmp_size -= len(dummy_content)
		# change a random byte in dummy content to avoid repeated hash values per block
		dummy_content[random.randrange(0, len(dummy_content))] = random.getrandbits(8)

	fp.write(dummy_content[:tmp_size])
	# change dummy content to avoid repeats
	dummy_content = bytearray(random.getrandbits(8) for _ in range(settings.blockSize))



###### measure results of addition
# get values
tmp_time = time.time()
N_requests = monitor.client.N_requests

# find changes, update index and blocks
monitor.find_changes()

# measure and display results
addition_elapsed_time = time.time() - tmp_time
addition_changed_blocks = monitor.client.N_requests - N_requests


print("\n========= Results for the additions - adding "+str(len(add_new_files)) + " files")
print("Time used to adjust index file and create new blocks: " + str(addition_elapsed_time) + "s")
print("Number of blocks used to store all newly added files: " + str(addition_changed_blocks) + " blocks")

index_file_size = os.path.getsize(settings.index_file)
content_used_blocks = monitor.index['general']['last_block_id'] - len(monitor.index['general']['deleted_blocks'])
total_files_size = sum(files.values())
print("Size of the index file: " + str(index_file_size) + " bytes")
print("Number of blocks used to store all files: " + str(content_used_blocks) + " blocks")
print("Required server storage: " + str((content_used_blocks*settings.blockSize)/1000/1000) + "mb")
print("Total size of files: " + str(total_files_size/1000/1000) + "mb")
print("Efficiency of storage: " + str(round(total_files_size/(content_used_blocks*settings.blockSize)*100, 2)) + "%")





################## test updates
##### moving files added during addition test to special dir
move_files = []
for file in files:
	# 1b-1kb files: 	
	if file.startswith('small_files_added/'):
		move_files.append(file)
	elif file.startswith('medium_files_added/'):
		move_files.append(file)

move_files.append('large_1MB')
move_files.append('large_3MB')
move_files.append('large_5MB')
move_files.append('large_10MB')
move_files.append('large_25MB')
move_files.append('large_50MB')

# move files from location to new dir
os.mkdir(settings.source_directory + '/moved_files')
for filename in move_files:
	tmp_basename = os.path.basename(filename)
	new_file = 'moved_files/' + tmp_basename
	shutil.move(settings.source_directory + '/' + filename, settings.source_directory + '/' + new_file)

	# adjust files array
	files[new_file] = files[filename]
	del files[filename]

# remove old (empty) dirs
shutil.rmtree(settings.source_directory + '/small_files_added')
shutil.rmtree(settings.source_directory + '/medium_files_added')

#### parse and display changes
# get values
tmp_time = time.time()
N_requests = monitor.client.N_requests

# find changes, update index and blocks
monitor.find_changes()

# measure and display results
update_elapsed_time = time.time() - tmp_time
update_changed_blocks = monitor.client.N_requests - N_requests


print("\n========= Results for the updates - moving "+str(len(move_files))+" files")
print("Time used to adjust index file and blocks: " + str(update_elapsed_time) + "s")
# print("Size of the index file: " + str(index_file_size) + " bytes")
print("Number of blocks updated to store all changes: " + str(update_changed_blocks) + " blocks")

index_file_size = os.path.getsize(settings.index_file)
content_used_blocks = monitor.index['general']['last_block_id'] - len(monitor.index['general']['deleted_blocks'])
total_files_size = sum(files.values())
print("Size of the index file: " + str(index_file_size) + " bytes")
print("Number of blocks used to store all files: " + str(content_used_blocks) + " blocks")
print("Required server storage: " + str((content_used_blocks*settings.blockSize)/1000/1000) + "mb")
print("Total size of files: " + str(total_files_size/1000/1000) + "mb")
print("Efficiency of storage: " + str(round(total_files_size/(content_used_blocks*settings.blockSize)*100, 2)) + "%")



################# sort files for increasing and decreasing file sizes, as well as files for editing content
files_increase_size = []
files_decrease_size = []
files_change_content = []
for file in files:
	# increasing/decreasing file sizes
	if file.startswith('small_files/'):
		if files[file] % 2 == 1:
			files_increase_size.append(file)
		else:
			files_decrease_size.append(file)
	elif file.startswith('medium_files/'):
		if files[file]/1000 % 2 == 1:
			files_increase_size.append(file)
		else:
			files_decrease_size.append(file)
	elif file.startswith('large_files/'):
		# sort uneven and even file sizes
		filesize = int(os.path.basename(file).strip('mb.txt'))
		if filesize > 10:
			filesize /= 10
		# uneven (1mb.txt, 3mb.txt, 5mb.txt, 7mb.txt, 9mb.txt, 30mb.txt, 50mb.txt, 70mb.txt, 90mb.txt)
		if filesize %2 == 1:
			files_increase_size.append(file)
		# even (2,4,6,8,10,20,40,60,80,100)mb.txt
		else:
			files_decrease_size.append(file)

	# editing content
	elif file.startswith('moved_files/'):
		files_change_content.append(file)


###################### update - reducing file sizes
for file in files_decrease_size:
	tmp_path = settings.source_directory + '/' + file
	# read content
	file_content = None
	new_file_length = math.ceil(files[file]/2)
	with open(tmp_path, 'rb') as tmp_fp_read:
		file_content = tmp_fp_read.read(new_file_length)
	# write file
	with open(tmp_path, 'wb') as tmp_fp_write:
		tmp_fp_write.write(file_content)
	files[file] = new_file_length


###### measure results of update - reducing file sizes
# get values
tmp_time = time.time()
N_requests = monitor.client.N_requests

# find changes, update index and blocks
monitor.find_changes()

# measure and display results
update_elapsed_time = time.time() - tmp_time
update_changed_blocks = monitor.client.N_requests - N_requests


print("\n========= Results for the updates - reducing file sizes of " + str(len(files_decrease_size)) + " files")
print("Time used to adjust index file and blocks: " + str(update_elapsed_time) + "s")
# print("Size of the index file: " + str(index_file_size) + " bytes")
print("Number of blocks updated to store all changes: " + str(update_changed_blocks) + " blocks")


index_file_size = os.path.getsize(settings.index_file)
content_used_blocks = monitor.index['general']['last_block_id'] - len(monitor.index['general']['deleted_blocks'])
total_files_size = sum(files.values())
print("Size of the index file: " + str(index_file_size) + " bytes")
print("Number of blocks used to store all files: " + str(content_used_blocks) + " blocks")
print("Required server storage: " + str((content_used_blocks*settings.blockSize)/1000/1000) + "mb")
print("Total size of files: " + str(total_files_size/1000/1000) + "mb")
print("Efficiency of storage: " + str(round(total_files_size/(content_used_blocks*settings.blockSize)*100, 2)) + "%")



################################# increasing file sizes
for file in files_increase_size:
	tmp_path = settings.source_directory + '/' + file
	# read content
	file_content = None
	file_length = files[file]
	with open(tmp_path, 'rb') as tmp_fp_read:
		file_content = tmp_fp_read.read(file_length)
	# write file (double content)
	with open(tmp_path, 'wb') as tmp_fp_write:
		tmp_fp_write.write(file_content)
		tmp_fp_write.write(file_content)
	files[file] = file_length*2



###### measure results of update - increasing file sizes
# get values
tmp_time = time.time()
N_requests = monitor.client.N_requests

# find changes, update index and blocks
monitor.find_changes()

# measure and display results
update_elapsed_time = time.time() - tmp_time
update_changed_blocks = monitor.client.N_requests - N_requests


print("\n========= Results for the updates - increasing file sizes of " + str(len(files_increase_size)) + " files")
print("Time used to adjust index file and blocks: " + str(update_elapsed_time) + "s")
# print("Size of the index file: " + str(index_file_size) + " bytes")
print("Number of blocks updated to store all changes: " + str(update_changed_blocks) + " blocks")


index_file_size = os.path.getsize(settings.index_file)
content_used_blocks = monitor.index['general']['last_block_id'] - len(monitor.index['general']['deleted_blocks'])
total_files_size = sum(files.values())
print("Size of the index file: " + str(index_file_size) + " bytes")
print("Number of blocks used to store all files: " + str(content_used_blocks) + " blocks")
print("Required server storage: " + str((content_used_blocks*settings.blockSize)/1000/1000) + "mb")
print("Total size of files: " + str(total_files_size/1000/1000) + "mb")
print("Efficiency of storage: " + str(round(total_files_size/(content_used_blocks*settings.blockSize)*100, 2)) + "%")


################################ changing file content
for file in files_change_content:
	with open(settings.source_directory + '/' + file, 'r+b') as tmp_fp:
		mid_pos = math.ceil(files[file]/2)-1
		# read byte on mid_pos
		tmp_fp.seek(mid_pos)
		tmp_content_byte = tmp_fp.read(1)
		# write changed byte to mid_pos
		tmp_content_byte = bytearray([(int.from_bytes(tmp_content_byte, 'little')+1)%256]) # increment byte by a single value (256 => 0)
		tmp_fp.seek(-1, 1)
		tmp_fp.write(tmp_content_byte)


##### measure results of update - changing file content
# get values
tmp_time = time.time()
N_requests = monitor.client.N_requests

# find changes, update index and blocks
monitor.find_changes()

# measure and display results
update_elapsed_time = time.time() - tmp_time
update_changed_blocks = monitor.client.N_requests - N_requests


print("\n========= Results for the updates - changing a byte in " + str(len(files_change_content)) + " files")
print("Time used to adjust index file and blocks: " + str(update_elapsed_time) + "s")
# print("Size of the index file: " + str(index_file_size) + " bytes")
print("Number of blocks updated to store all changes: " + str(update_changed_blocks) + " blocks")


index_file_size = os.path.getsize(settings.index_file)
content_used_blocks = monitor.index['general']['last_block_id'] - len(monitor.index['general']['deleted_blocks'])
total_files_size = sum(files.values())
print("Size of the index file: " + str(index_file_size) + " bytes")
print("Number of blocks used to store all files: " + str(content_used_blocks) + " blocks")
print("Required server storage: " + str((content_used_blocks*settings.blockSize)/1000/1000) + "mb")
print("Total size of files: " + str(total_files_size/1000/1000) + "mb")
print("Efficiency of storage: " + str(round(total_files_size/(content_used_blocks*settings.blockSize)*100, 2)) + "%")


################ test deletions
# delete all files
for file in files:
	os.remove(settings.source_directory + '/' + file)


###### measure results of deletion
tmp_time = time.time()
N_requests = monitor.client.N_requests

# find changes, update index and blocks
monitor.find_changes()

# measure and display results
deletion_elapsed_time = time.time() - tmp_time
deletion_changed_blocks = monitor.client.N_requests - N_requests


print("\n========= Results for the deletions - deleting " + str(len(files)) + " files")
print("Time used to adjust index file and create new blocks: " + str(deletion_elapsed_time) + "s")
print("Number of blocks used to store all newly added files: " + str(deletion_changed_blocks) + " blocks")

index_file_size = os.path.getsize(settings.index_file)
print("Size of the index file: " + str(index_file_size) + " bytes")

