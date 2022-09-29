import math
import sys
import os
import random
import json
import time

from pprint import pprint
from settings import Settings
settings = Settings()

# ORAM implementation class (square-root ORAM)
class Sqrt():

		# init oram (Set properties and connect to server)
		def __init__(self, client):

			# square-root ORAM has a fixed-size shelter, this variable is used to ease oram measurement tests.
			self.local_max_shelter_size = 0
			self.number_eoe = 0
			self.time_eoe = 0
			self.N_requests_eoe = 0

			# init properties
			self.client = client
			self.shelter = []
			self.index = self.read_index()

			# index has not yet been created -> create it and store in settings.oram_index_file
			if self.index == {}:
				# print("No file index found - generate new index file")

				# create index local variables
				self.init_oram()

				# write index to settings.oram_index_file
				self.update_index()


		# read index file (and shelter) and return data
		def read_index(self):
			if os.path.exists(settings.oram_index_file):
				with open(settings.oram_index_file, 'r') as index_file:
					self.index = json.load(index_file)

					# index of other ORAM type: error
					if self.index['general']['oram_type'] != settings.oram:
						print("Found oram index for oram type: " + str(self.index['general']['oram_type']) + ".\nPlease remove it to continue.")
						exit()

					# init shelter
					self.shelter = [None]*self.index['general']['S']

					# set local shelter size
					self.local_max_shelter_size = int(self.index['general']['S'])

					# read cache file
					with open(settings.oram_cache_file, 'rb') as cache_file:
						for i in range(0, len(self.shelter)):
							self.shelter[i] = bytes(cache_file.read(settings.blockSize))
							if self.index['shelter'][i] == None:
								# shelter read dummy content, overwrite with None
								self.shelter[i] = None

			else:
				self.index = {}

			return self.index

		# write/update self.index to settings.index_file, as well as write the shelter to the cache file
		def update_index(self):
			# write index
			with open(settings.oram_index_file, 'w') as index_file:
				json.dump(self.index, index_file)

			# write shelter
			with open(settings.oram_cache_file, 'wb') as cache_file:
				for el in self.shelter:
					if el != None and len(el) == settings.blockSize:
						cache_file.write(el)
					else:
						# write dummy
						cache_file.write(self.client.generate_dummy_block())




		# initialize ORAM structure and local variables
		def init_oram(self):
			max_server_blocks = settings.N_blocks# number of blocks on server
			
			# server has storage of N and shelter of sqrt(N), calculate N so that server storage + shelter fits in max_server_blocks
			N = 0
			for i in range(1, max_server_blocks):
				tmp_shelter_size = i**0.5
				if math.ceil(i + tmp_shelter_size) > max_server_blocks:
					break

				if tmp_shelter_size.is_integer():
					N = i
			S = int(N**0.5)

			# S = shelter size (and number of dummies, sqrt N, stored on the server)
			# N = number of blocks stored on server (excluding dummies)
			self.index['general'] = {
				'oram_type': settings.oram,
				'N' : N,
				'S': S,
				'cnt': 0 # count through epoch to determine which dummy block to request from the server
			}

			# create clientside shelter
			self.index['shelter'] = [None]*S
			self.shelter = [None]*S


			### Create oblivious permutation map (position map), mapping virtual address (block_id/dummy_block_id) to server-side blocks
			self.index['pos_map'] = {}
			pos_map_rand = {}
			for i in range(1, N+S+1):
				tmp_rand = random.randrange(1, N*2) # N*3 > N+S+1
				while tmp_rand in pos_map_rand.values():
					tmp_rand = random.randrange(1, N*2)

				pos_map_rand[i] = tmp_rand

			sequence = sorted(pos_map_rand.values())
			for i in range(1, N+S+1):
				self.index['pos_map'][str(i)] = sequence.index(pos_map_rand[i])+1

			# set local shelter size
			self.local_max_shelter_size = int(self.index['general']['S'])




		# Read(data=None) or Write(data=bytes) operation
		def access(self, block_id, data=None):
			# error handling
			if block_id <= 0 or block_id > self.index['general']['N']:
				print("Invalid block: " + str(block_id))
				exit()

			# see if block_id is in shelter
			block_in_shelter = block_id in self.index['shelter']
			shelter_index = self.shelter.index(None) # first empty spot in shelter

			# block is already in shelter, shelter index must be changed to match
			if block_in_shelter:
				shelter_index = self.index['shelter'].index(block_id)

			# find mapped block to request
			mapped_block_id = self.index['pos_map'][str(block_id)]
			# block is already in shelter, request dummy block
			if block_in_shelter:
				# dummy block = N+cnt+1 (N+1 is first dummy block)
				mapped_block_id = self.index['pos_map'][str(self.index['general']['S'] + self.index['general']['cnt'] + 1)] 

			result = self.client._send("R", mapped_block_id, self.client.generate_dummy_block())

			# store in shelter if this is a new request, and not a dummy value
			if block_in_shelter == False and len(result) >= settings.blockSize:
				self.index['shelter'][shelter_index] = block_id
				self.shelter[shelter_index] = result[:settings.blockSize]

			# read operation, get result from shelter
			if block_in_shelter == True and data == None:
				result = self.shelter[shelter_index]

			# Write operation (write data to shelter)
			if data != None and len(data) == settings.blockSize:
				self.shelter[shelter_index] = data

			# increase cnt
			self.index['general']['cnt'] += 1
		
			# write results to index and cache file
			self.update_index()

			# end of epoch?
			if self.index['general']['cnt'] >= self.index['general']['S']:
				self.end_of_epoch()

			return result

		# find first key in dict that matches value val.
		def getKeyFromValueDict(self, dictionary, val):
			for key, value in dictionary.items():
				if value == val:
					return key

			return None

		# read all memory, resort position map and upload all content (memory+shelter)
		def end_of_epoch(self):
			if self.index['general']['cnt'] < self.index['general']['S']:
				print("Called end-of-epoch without enough requests")
				return
			
			# print("SQRT ORAM - END OF EPOCH")

			# update counters
			self.number_eoe += 1
			tmp_time = time.time()
			tmp_N_requests = self.client.N_requests
			
			## create new position map
			new_position_map = {}
			pos_map_rand = {}
			for i in range(1, self.index['general']['N']+self.index['general']['S']+1):
				tmp_rand = random.randrange(1, self.index['general']['N']*2) # N*2 > N+S+1
				while tmp_rand in pos_map_rand.values():
					tmp_rand = random.randrange(1, self.index['general']['N']*2)

				pos_map_rand[i] = tmp_rand

			sequence = sorted(pos_map_rand.values())
			for i in range(1, self.index['general']['N']+self.index['general']['S']+1):
				new_position_map[str(i)] = sequence.index(pos_map_rand[i])+1


			## upload shelter content, read server memory to shelter, and re-upload
			virtual_address_status = [False]*(self.index['general']['N']+self.index['general']['S']+1) #True=>uploaded to server
			virtual_address_status[0] = True # block_id 0 does not exist, hence default to True

			# continue until all addresses are written once
			while not all(virtual_address_status):
				empty_shelter = True

				# switch elements in shelter (if a dummy value is read, empty shelter entry)
				for i in range(0, len(self.index['shelter'])):
					# empty?
					if self.index['shelter'][i] == None: 
						continue;

					# shelter is not empty
					empty_shelter = False

					# write content of shelter to new position
					tmp_block_id = self.index['shelter'][i]
					tmp_content = self.client._send("W", new_position_map[str(tmp_block_id)], self.shelter[i])
					virtual_address_status[tmp_block_id] = True

					# see if returned value matches a block
					prev_block_id = int(self.getKeyFromValueDict(self.index['pos_map'], new_position_map[str(tmp_block_id)]))

					# see if previous block is not a dummy, and has not yet been uploaded (or stored in shelter): store in shelter
					if virtual_address_status[prev_block_id] == False and prev_block_id <= self.index['general']['N'] and prev_block_id not in self.index['shelter']:
						self.index['shelter'][i] = prev_block_id
						self.shelter[i] = tmp_content[:settings.blockSize]
					# empty shelter entry
					else:
						self.index['shelter'][i] = None
						self.shelter[i] = None

				# shelter is empty, write dummy values to dummy blocks in order to re-fill shelter
				if empty_shelter:
					shelter_index = 0
					for dummy_block_id in range(self.index['general']['N']+1, self.index['general']['N']+self.index['general']['S']+1):
						# dummy value not yet written
						if virtual_address_status[dummy_block_id] == False:

							# write dummy value, record result and store in shelter(if appropiate)
							tmp_content = self.client._send("W", new_position_map[str(dummy_block_id)], self.client.generate_dummy_block())
							virtual_address_status[dummy_block_id] = True

							# see if returned value matches a block
							prev_block_id = int(self.getKeyFromValueDict(self.index['pos_map'], new_position_map[str(dummy_block_id)]))

							# write block to shelter
							# see if previous block is not a dummy, and has not yet been uploaded: store in shelter
							if not virtual_address_status[prev_block_id] and prev_block_id <= self.index['general']['N']:
								self.index['shelter'][shelter_index] = prev_block_id
								self.shelter[shelter_index] = tmp_content[:settings.blockSize]

								# shelter is no longer empty
								empty_shelter = False

								# increment shelter index
								shelter_index += 1

								# see if shelter is full (should never happen)
								if shelter_index >= len(self.shelter):
									break
							

				# any missed blocks that should be read from the server first
				if empty_shelter:
					# find first false entry
					virtual_block_index = 0
					try:
						virtual_block_id = virtual_address_status.index(False)
						self.index['shelter'][0] = virtual_block_id
						tmp_res = self.client._send("R", self.index['pos_map'][str(virtual_block_id)], self.client.generate_dummy_block())
						self.shelter[0] = tmp_res[:settings.blockSize]
						empty_shelter = False

					except ValueError:
						pass


			# update counters
			self.time_eoe += (time.time() - tmp_time)
			self.N_requests_eoe += self.client.N_requests - tmp_N_requests


			## write results to index and cache file
			self.index['pos_map'] = new_position_map
			self.index['general']['cnt'] = 0
			self.update_index()



