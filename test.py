from client import Client
from pprint import pprint
from monitor import Monitor
import random
import os
from settings import Settings
settings = Settings()


############## file conversion test - generate index
if True:#:settings.oram == None:
	pprint("Remove index file")
	# os.remove(settings.index_file)
	

	##### create files of sizes 1KB - 1MB
	files = {}
	for i in range(10, 100):
		files[str(i)+'kb.txt'] = 1000*i

	# write all files to source directory
	dummy_content = bytearray(random.getrandbits(8) for _ in range(settings.blockSize))
	for file in files:
		# write file of size files[file] 
		fp = open(settings.source_directory + '/'  + file, 'wb')
		tmp_size = files[file]
		while tmp_size > len(dummy_content):
			fp.write(dummy_content)
			tmp_size -= len(dummy_content)
			# change a random byte in dummy content to avoid repeated hash values per block
			dummy_content[random.randrange(0, len(dummy_content))] = random.getrandbits(8)

		fp.write(dummy_content[:tmp_size])
		fp.close()
		# change dummy content to avoid repeats
		dummy_content = bytearray(random.getrandbits(8) for _ in range(settings.blockSize))

	# input()

	# create monitor (and init empty database)
	monitor = Monitor(clear_database=True)

	##### double content of files
	for file in files:
		# read content
		file_content = None
		file_length = files[file]
		tmp_path = settings.source_directory + '/' + file
		with open(tmp_path, 'rb') as tmp_fp_read:
			file_content = tmp_fp_read.read(file_length)
		# write file (double content)
		with open(tmp_path, 'wb') as tmp_fp_write:
			tmp_fp_write.write(file_content)
			tmp_fp_write.write(file_content)
		files[file] = file_length*2

	# input()
	monitor.find_changes()


	# compare content
	for file in files:
		file_path = settings.source_directory + '/' + file

		file_content = monitor.download_file(file_path)
		local_file_content = None
		with open(file_path, 'rb') as tmp_fp_read:
			local_file_content = tmp_fp_read.read(files[file])

		if file_content == local_file_content:
			pprint("MATCH OF file: " + str(file))
		else:
			pprint("INCORRECT MATCH OF FILE: " + str(file))
			pprint("downloaded len: " + str(len(file_content)) + ", local len: " + str(len(local_file_content)))
			pprint("Type download: " + str(type(file_content)) + ", type local: " + str(type(local_file_content)))
			print(file_content)
			print("====================================================")
			print(local_file_content)
			# input()


	exit()

########### ORAM TEST 
# remove oram index
os.remove(settings.oram_index_file)

# init client and reset server-side database files 
client = Client()
client.reset_database()

# client.read(40)
# exit()

# exit()
# testMessage = bytearray(random.getrandbits(8) for _ in range(settings.blockSize))
# print(testMessage)
# create_database()
testMessages  = []
for i in range(0, 1000):
	testMessages.append(client.padd_content(bytes(("test message #"+str(i)+" ").encode())))


for i in range(1, len(testMessages)):
	pprint("Write #" + str(i))
	client.write(i, testMessages[i])
	# input()


for i in range(1, len(testMessages)):
	# print("Read #" + str(i))
	# input()
	tmp_data = client.read(i)
	if tmp_data == testMessages[i]:
		pprint("Message #" + str(i) + " matches")
	else:
		pprint("ERROR: Message #" + str(i) + " failed. len_data="+str(len(tmp_data)) + ", len_test="+str(len(testMessages[i])))
		pprint(tmp_data[:20])
		pprint(testMessages[i][:20])
		input()
	# input()

if settings.oram == 'trivial':
	pprint("Failed additions count: " + str(client.oram.failed_additions_count))


# client._send("W", 3, testMessages[4])
# pprint(client._send("R", 3, testMessages[3]))
exit()

# client.read(13)
pprint("RES:")
client.write(1, testMessages[1])
# client.write(2, testMessages[2])

# course code (for OWAS): 192199978