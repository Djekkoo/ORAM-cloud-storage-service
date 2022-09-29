### Code to measure the oram efficiency
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

# set test properties
initial_block_load = 0.0 # blocks loaded during initialisation, set as default load to perform measurements over. In percentage of max load
added_block_load = 500 # blocks added during add-measurement
increased_block_load = 500 # number of blocks added to already existing files



# ensure accidental activation of this script does not remove the regular testing directory
if settings.source_directory == './storage':
	print("Settings source directory is default \'./storage\', please change it to a directory that can be overwritten for testing")
	exit()

if settings.oram == None:
	print("ORAM method(settings.oram) has not been set, please change it to a valid value (sqrt/trivial/pathoram)")
	exit()

# remove existing files(and directory) in source(test) directory
if os.path.exists(settings.source_directory):
	shutil.rmtree(settings.source_directory)

# create specific testing directory for monitoring and file conversion script
os.mkdir(settings.source_directory)

# display testing configuration
print("Measure oram script with the following file conversion settings:")
print("Block size: " + str(settings.blockSize))
print("Use file hash: " + str(settings.file_hash))
print("Use block hash: " + str(settings.block_hash))
print("Use extends: " + str(settings.blocks_use_extends))

print("\nThe following ORAM settings are used:")
print("Testing ORAM type: " + str(settings.oram))
if settings.oram == 'trivial' or settings.oram == 'pathoram':
	print("Each bucket contains: " + str(settings.oram_Z_blocks_per_bucket) + " blocks")
if settings.oram == 'trivial':
	print("Eviction rate(z) is: " + str(settings.oram_eviction_rate) + " buckets per layer")

# print("Server capacity: " + str(settings.N_blocks) + " blocks")


# create monitor (and init empty database)
monitor = Monitor(clear_database=True)

# calculate maximum storage size of server (in blocks)
oram_max_size = 0
if settings.oram == 'trivial' or settings.oram == 'pathoram':
	oram_max_size = monitor.client.oram.index['general']['N_buckets']*settings.oram_Z_blocks_per_bucket
elif settings.oram == 'sqrt':
	oram_max_size = monitor.client.oram.index['general']['N']

print("Max server storage size: " + str(oram_max_size) + " blocks\n")

# set initial load to percentage of max load
initial_block_load = int(initial_block_load*oram_max_size)


# input()
####### init standard load in database
print("Creating initial files to create a server load in the ORAM before testing.")

# create files
os.mkdir(settings.source_directory + '/init-files')
create_block_load = initial_block_load
initial_files = {}
last_file_index = 0
# create files with 10 blocks in size
while create_block_load >= 10:
	last_file_index += 1
	tmp_file = settings.source_directory + '/init-files/'  + str(last_file_index) + '.txt'
	fp = open(tmp_file, 'wb')
	fp.write(bytearray(random.getrandbits(8) for _ in range(settings.blockSize*10)))
	fp.close()
	create_block_load -= 10
	initial_files[tmp_file] = 10

# create last file (with less then 10 blocks in size?)
if create_block_load > 0:
	last_file_index += 1
	tmp_file = settings.source_directory + '/init-files/'  + str(last_file_index) + '.txt'
	fp = open(tmp_file, 'wb')
	fp.write(bytearray(random.getrandbits(8) for _ in range(settings.blockSize*create_block_load)))
	fp.close()
	initial_files[tmp_file] = create_block_load
	create_block_load = 0

# create ORAM-type dependent measurement variables
trivial_failed_evictions = 0
sqrt_end_of_epoch_N = 0
sqrt_end_of_epoch_time = 0

# store previous measurements
tmp_network_requests = monitor.client.N_requests
tmp_time = time.time()
oram_time = monitor.client.oram_time_elapsed

if settings.oram == 'sqrt':
	sqrt_end_of_epoch_N = monitor.client.oram.number_eoe
	sqrt_end_of_epoch_time = monitor.client.oram.time_eoe
	sqrt_end_of_epoch_N_requests = monitor.client.oram.N_requests_eoe
if settings.oram == 'trivial':
	trivial_failed_evictions = monitor.client.oram.failed_evictions_count


# init default load
monitor.find_changes()


# compare measurements
tmp_network_requests = monitor.client.N_requests - tmp_network_requests
tmp_time = time.time() - tmp_time
oram_time = monitor.client.oram_time_elapsed-oram_time

if settings.oram == 'sqrt':
	sqrt_end_of_epoch_N = monitor.client.oram.number_eoe - sqrt_end_of_epoch_N
	sqrt_end_of_epoch_time = monitor.client.oram.time_eoe - sqrt_end_of_epoch_time
	sqrt_end_of_epoch_N_requests = monitor.client.oram.N_requests_eoe - sqrt_end_of_epoch_N_requests
if settings.oram == 'trivial':
	trivial_failed_evictions = monitor.client.oram.failed_evictions_count - trivial_failed_evictions


print("ORAM has been initialised with "+str(len(initial_files))+" files composed of " + str(initial_block_load) + " blocks. ")
print("Performed " + str(tmp_network_requests) + " network requests")
print("The maximum shelter size has reached " + str(monitor.client.oram.local_max_shelter_size) + " blocks")
print("Local oram index file size: " + str(os.path.getsize(settings.oram_index_file)) + " bytes")
print("Local file conversion index file size: " + str(os.path.getsize(settings.index_file)) + " bytes")
print("ORAM has been initialised with " + str(initial_block_load) + " blocks. Prepare for standard testing and measurements.")
print("The total execution duration is: "+str(round(tmp_time, 2))+" seconds (file conversion+ORAM)")
print("The ORAM execution duration is: " + str(round(oram_time, 2)) + " seconds")
if settings.oram == 'sqrt':
	print("Number of end-of-epoch invocations: " + str(sqrt_end_of_epoch_N) + " times")
	print("Total duration of end-of-epoch invocations: " + str(round(sqrt_end_of_epoch_time, 2)) + " s")
	print("Number of network requests performed during end-of-epoch invocations: " + str(sqrt_end_of_epoch_N_requests) + " requests")
if settings.oram == 'trivial':
	print("Number of failed evictions: " + str(trivial_failed_evictions) + " times")

print("Server load= " + str(initial_block_load) + "/" + str(oram_max_size) + " = " + str(round(initial_block_load/oram_max_size*100, 2)) + "%\n")


##### Add files (blocks)
os.mkdir(settings.source_directory + '/add-files')
tmp_add_load = added_block_load
added_files = {}
last_file_index = 0
# create files with 10 blocks in size
while tmp_add_load >= 10:
	last_file_index += 1
	tmp_file = settings.source_directory + '/add-files/'  + str(last_file_index) + '.txt'
	fp = open(tmp_file, 'wb')
	fp.write(bytearray(random.getrandbits(8) for _ in range(settings.blockSize*10)))
	fp.close()
	tmp_add_load -= 10
	added_files[tmp_file] = 10

# create last file (with less then 10 blocks in size?)
if tmp_add_load > 0:
	last_file_index += 1
	tmp_file = settings.source_directory + '/add-files/'  + str(last_file_index) + '.txt'
	fp = open(tmp_file, 'wb')
	fp.write(bytearray(random.getrandbits(8) for _ in range(settings.blockSize*tmp_add_load)))
	fp.close()
	added_files[tmp_file] = tmp_add_load
	tmp_add_load = 0

# store previous measurements
tmp_network_requests = monitor.client.N_requests
tmp_time = time.time()
oram_time = monitor.client.oram_time_elapsed

if settings.oram == 'sqrt':
	sqrt_end_of_epoch_N = monitor.client.oram.number_eoe
	sqrt_end_of_epoch_time = monitor.client.oram.time_eoe
	sqrt_end_of_epoch_N_requests = monitor.client.oram.N_requests_eoe
if settings.oram == 'trivial':
	trivial_failed_evictions = monitor.client.oram.failed_evictions_count


# update monitor (and upload files using oram)
monitor.find_changes()

# compare measurements
tmp_network_requests = monitor.client.N_requests - tmp_network_requests
tmp_time = time.time() - tmp_time
oram_time = monitor.client.oram_time_elapsed-oram_time

if settings.oram == 'sqrt':
	sqrt_end_of_epoch_N = monitor.client.oram.number_eoe - sqrt_end_of_epoch_N
	sqrt_end_of_epoch_time = monitor.client.oram.time_eoe - sqrt_end_of_epoch_time
	sqrt_end_of_epoch_N_requests = monitor.client.oram.N_requests_eoe - sqrt_end_of_epoch_N_requests
if settings.oram == 'trivial':
	trivial_failed_evictions = monitor.client.oram.failed_evictions_count - trivial_failed_evictions

print("ORAM has added "+str(len(added_files))+" files composed of " + str(added_block_load) + " blocks. ")
print("Performed: " + str(tmp_network_requests) + "(total: "+str(monitor.client.N_requests)+") network requests")
print("The maximum shelter size has reached: " + str(monitor.client.oram.local_max_shelter_size) + " blocks")
print("Local oram index file size: " + str(os.path.getsize(settings.oram_index_file)) + " bytes")
print("Local file conversion index file size: " + str(os.path.getsize(settings.index_file)) + " bytes")
print("The total execution duration is: "+str(round(tmp_time, 2))+" seconds (file conversion+ORAM)")
print("The ORAM execution duration is: " + str(round(oram_time, 2)) + " seconds")

if settings.oram == 'sqrt':
	print("Number of end-of-epoch invocations: " + str(sqrt_end_of_epoch_N) + " times")
	print("Total duration of end-of-epoch invocations: " + str(round(sqrt_end_of_epoch_time, 2)) + " s")
	print("Number of network requests performed during end-of-epoch invocations: " + str(sqrt_end_of_epoch_N_requests) + " requests")
if settings.oram == 'trivial':
	print("Number of failed evictions: " + str(trivial_failed_evictions) + " times")

print("Server load= " + str(added_block_load+initial_block_load) + "/" + str(oram_max_size) + " = " + str(round((initial_block_load+added_block_load)/oram_max_size*100, 2)) + "%\n")




####### increase files 
updated_files = [] # only valid when block_hash is false
for i in range(0, increased_block_load):
	# write a block of data to a random (added) file.
	file_entry = random.choice(list(added_files))
	fp = open(file_entry, "ab")
	fp.write(bytearray(random.getrandbits(8) for _ in range(settings.blockSize)))
	fp.close()
	added_files[file_entry] += 1
	if file_entry not in updated_files:
		updated_files.append(file_entry)
	

# calculate updated blocks (when block hash is false)
updated_blocks = 0
for file in updated_files:
	updated_blocks += added_files[file]



# store previous measurements
tmp_network_requests = monitor.client.N_requests
tmp_time = time.time()
oram_time = monitor.client.oram_time_elapsed

if settings.oram == 'sqrt':
	sqrt_end_of_epoch_N = monitor.client.oram.number_eoe
	sqrt_end_of_epoch_time = monitor.client.oram.time_eoe
	sqrt_end_of_epoch_N_requests = monitor.client.oram.N_requests_eoe
if settings.oram == 'trivial':
	trivial_failed_evictions = monitor.client.oram.failed_evictions_count


# update monitor (and upload changes using oram)
monitor.find_changes()

# compare measurements
tmp_network_requests = monitor.client.N_requests - tmp_network_requests
tmp_time = time.time() - tmp_time
oram_time = monitor.client.oram_time_elapsed-oram_time

if settings.oram == 'sqrt':
	sqrt_end_of_epoch_N = monitor.client.oram.number_eoe - sqrt_end_of_epoch_N
	sqrt_end_of_epoch_time = monitor.client.oram.time_eoe - sqrt_end_of_epoch_time
	sqrt_end_of_epoch_N_requests = monitor.client.oram.N_requests_eoe - sqrt_end_of_epoch_N_requests
if settings.oram == 'trivial':
	trivial_failed_evictions = monitor.client.oram.failed_evictions_count - trivial_failed_evictions

# make adjustments in messaging if block_hash is False

print("ORAM has increased the file sizes of the previously added files with a total of " + str(increased_block_load) + " blocks. ")
# block hash is false, updated files will be completely re-uploaded
if settings.block_hash == False:
	print("Because block_hash is false, this update operation has re-uploaded " + str(len(updated_files)) +" files composed of " + str(updated_blocks) + " blocks")
print("Performed: " + str(tmp_network_requests) + "(total: "+str(monitor.client.N_requests)+") network requests")
print("The maximum shelter size has reached: " + str(monitor.client.oram.local_max_shelter_size) + " blocks")
print("Local oram index file size: " + str(os.path.getsize(settings.oram_index_file)) + " bytes")
print("Local file conversion index file size: " + str(os.path.getsize(settings.index_file)) + " bytes")
print("The total execution duration is: "+str(round(tmp_time, 2))+" seconds (file conversion+ORAM)")
print("The ORAM execution duration is: " + str(round(oram_time, 2)) + " seconds")

if settings.oram == 'sqrt':
	print("Number of end-of-epoch invocations: " + str(sqrt_end_of_epoch_N) + " times")
	print("Total duration of end-of-epoch invocations: " + str(round(sqrt_end_of_epoch_time, 2)) + " s")
	print("Number of network requests performed during end-of-epoch invocations: " + str(sqrt_end_of_epoch_N_requests) + " requests")
if settings.oram == 'trivial':
	print("Number of failed evictions: " + str(trivial_failed_evictions) + " times")

print("Server load= " + str(added_block_load+initial_block_load+increased_block_load) + "/" + str(oram_max_size) + " = " + str(round((initial_block_load+added_block_load+increased_block_load)/oram_max_size*100, 2)) + "%\n")



####### reading all files in added_files
# aggregate and previous measurements
total_reading_time = 0
tmp_network_requests = monitor.client.N_requests
oram_time = monitor.client.oram_time_elapsed
failed_files = []

if settings.oram == 'sqrt':
	sqrt_end_of_epoch_N = monitor.client.oram.number_eoe
	sqrt_end_of_epoch_time = monitor.client.oram.time_eoe
	sqrt_end_of_epoch_N_requests = monitor.client.oram.N_requests_eoe
if settings.oram == 'trivial':
	trivial_failed_evictions = monitor.client.oram.failed_evictions_count


# read every file
for file_path in added_files:

	# Download(read) file from ORAM and store execution duration
	tmp_time = time.time()
	file_content = monitor.download_file(file_path)
	total_reading_time += (time.time() - tmp_time)

	# read local file from file system
	local_file_content = None
	with open(file_path, 'rb') as tmp_fp_read:
		local_file_content = tmp_fp_read.read(added_files[file_path]*settings.blockSize)

	# compare results
	if file_content != local_file_content:
		failed_files.append(file_path)
		pprint("INCORRECT MATCH OF FILE: " + str(file_path))

# finish measurements
tmp_network_requests = monitor.client.N_requests - tmp_network_requests
oram_time = monitor.client.oram_time_elapsed - oram_time

if settings.oram == 'sqrt':
	sqrt_end_of_epoch_N = monitor.client.oram.number_eoe - sqrt_end_of_epoch_N
	sqrt_end_of_epoch_time = monitor.client.oram.time_eoe - sqrt_end_of_epoch_time
	sqrt_end_of_epoch_N_requests = monitor.client.oram.N_requests_eoe - sqrt_end_of_epoch_N_requests
if settings.oram == 'trivial':
	trivial_failed_evictions = monitor.client.oram.failed_evictions_count - trivial_failed_evictions

# display reading results
print("ORAM has read "+str(len(added_files))+" files composed of " + str(sum(added_files.values())) + " blocks. ")
print("Comparison with local file system has "+str(len(failed_files)) + " failed read operations")
print("Performed: " + str(tmp_network_requests) + "(total: "+str(monitor.client.N_requests)+") network requests")
print("The maximum shelter size has reached: " + str(monitor.client.oram.local_max_shelter_size) + " blocks")
print("Local oram index file size: " + str(os.path.getsize(settings.oram_index_file)) + " bytes")
print("Local file conversion index file size: " + str(os.path.getsize(settings.index_file)) + " bytes")
print("The total execution duration is: "+str(round(total_reading_time, 2))+" seconds (file conversion+ORAM)")
print("The ORAM execution duration is: " + str(round(oram_time, 2)) + " seconds")

if settings.oram == 'sqrt':
	print("Number of end-of-epoch invocations: " + str(sqrt_end_of_epoch_N) + " times")
	print("Total duration of end-of-epoch invocations: " + str(round(sqrt_end_of_epoch_time, 2)) + " s")
	print("Number of network requests performed during end-of-epoch invocations: " + str(sqrt_end_of_epoch_N_requests) + " requests")
if settings.oram == 'trivial':
	print("Number of failed evictions: " + str(trivial_failed_evictions) + " times")

print("Server load= " + str(added_block_load+initial_block_load+increased_block_load) + "/" + str(oram_max_size) + " = " + str(round((initial_block_load+added_block_load+increased_block_load)/oram_max_size*100, 2)) + "%\n")
