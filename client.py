import socket
import sys
import random
import secrets
import time
from pprint import pprint

import scrypt
import hashlib
from Crypto.Cipher import AES

from settings import Settings
settings = Settings()


# client class 
class Client():

    # init client (Set properties and connect to server)
    def __init__(self):
        # set local properties and measurement variables
        self.N_requests = 0
        self.oram_time_elapsed = 0
        self.oram = None
        self.server = None

        # load ORAM
        if settings.oram == 'sqrt':
            import oram.sqrt
            self.oram = oram.sqrt.Sqrt(self)
        elif settings.oram == 'pathoram':
            import oram.pathoram
            self.oram = oram.pathoram.Pathoram(self)
        elif settings.oram == 'trivial':
            import oram.trivial
            self.oram = oram.trivial.Trivial(self)

        # calculate 128-bit AES encryption key
        self.encryption_key = scrypt.hash(settings.encryption_password, hashlib.sha256(settings.encryption_password.encode()).hexdigest(), 16384, 8, 1, 16)

        # init server entry? 
        if settings.skip_network_connection:
            import server
            self.server = server.Server()

    def reset_database(self):
        # reset server database
        if self.server != None:
            self.server.create_database()


    # padds specific content with random bytes until it has the size of a block
    def padd_content(self, content):
        # length is already blockSize
        if len(content) == settings.blockSize:
            return content

        missing_bytes = settings.blockSize - len(content)
        return content + bytearray(secrets.token_bytes(missing_bytes))

    # generate dummy bytes with length blockSize
    def generate_dummy_block(self):
        return bytearray(secrets.token_bytes(settings.blockSize))


    def write(self, block_id, data):
        # no ORAM method is set, this means that there is no need to really store it to the server
        # this method is used to test the efficiency of the file conversion method, without the delay of communication between client+server
        if self.oram == None:
            self.N_requests += 1
            return

        # calculate duration of ORAM access
        tmp_time = time.time()
        result = self.oram.access(block_id, data)
        tmp_time = time.time()-tmp_time

        self.oram_time_elapsed += tmp_time

        return result



    def read(self, block_id):
        # no ORAM method is set, this means that there is no need to really store it to the server
        # this method is used to test the efficiency of the file conversion method, without the delay of communication between client+server
        if self.oram == None:
            self.N_requests += 1
            return

        # calculate duration of ORAM access
        tmp_time = time.time()
        result = self.oram.access(block_id)
        tmp_time = time.time()-tmp_time

        self.oram_time_elapsed += tmp_time

        return result


    # send message and receive response
    # command  = "R" or "W"
    def _send(self, command, server_block_id, data, client_block_id=None):

        # increment requests (called by ORAM scripts)
        self.N_requests += 1

        # encode client_block_id in data?
        client_block_encoding_length = 0
        if settings.oram == 'trivial' or settings.oram == 'pathoram': 
            # need dummy client block (=0)
            if client_block_id == None:
                client_block_id = 0

            # get encoding length
            client_block_encoding_length = len(str(settings.N_blocks))
            # padd client_block_id string
            client_block_id = str(client_block_id)
            client_block_id = "0"*(client_block_encoding_length-len(client_block_id)) + client_block_id 
            # append to data
            data += client_block_id.encode()

        # if command == 'W' and int(client_block_id) != 0:
        #     pprint("Write block " + str(client_block_id) + " to server address " + str(server_block_id))

        # encrypt data with AES(-128)
        aes_enc = AES.new(self.encryption_key, AES.MODE_CTR)
        data = aes_enc.encrypt(data)
        enc_nonce = aes_enc.nonce

        ## send data to the correct block
        received = None

        # communicate over network
        if settings.skip_network_connection == False:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((settings.HOST, settings.PORT))
            # send command and data
            pprint("Send command: " + str(command) + str(server_block_id))
            self.socket.send(bytes(command + str(server_block_id) + "\n", "utf-8"))
            pprint("Send data")
            self.socket.sendall(enc_nonce+data)
            # receive data
            pprint("receive data")
            received = bytearray(self.socket.recv(settings.blockSize+settings.encryption_nonce_length+client_block_encoding_length))
            self.socket.close()

        # communicate using code
        else:
            received = self.server.handle_request(bytes(command + str(server_block_id), "utf-8"), enc_nonce+data)

        # decrypt received with AES
        dec_nonce = received[:settings.encryption_nonce_length]
        received = received[settings.encryption_nonce_length:]
        aes_dec = AES.new(self.encryption_key, AES.MODE_CTR, nonce=dec_nonce)
        received = aes_dec.decrypt(received)

        # if client_block_id != None: split data and client_block_id
        if client_block_id != None:
            received_block_id = 0
            if len(received) > settings.blockSize:
                try:
                    received_block_id = int(received[settings.blockSize:].decode())
                except (UnicodeDecodeError, ValueError): # server-generated random bytes, cannot be decoded
                    received_block_id = 0
                received = received[:settings.blockSize]
            # if command == 'R' and int(received_block_id) != 0:
            #     pprint("Read block " + str(received_block_id) + " from server address " + str(server_block_id))
            return(received, received_block_id)

        # return result
        return received


