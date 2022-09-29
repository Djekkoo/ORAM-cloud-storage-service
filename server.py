import socketserver
import random
import secrets
import os
import shutil

from pprint import pprint
from settings import Settings
settings = Settings()
server = None

# determine length additions to blocks(trivial and pathoram add local block ID in blocks)
client_block_encoding_length = 0
if settings.oram == 'pathoram' or settings.oram == 'trivial':
    client_block_encoding_length = len(str(settings.N_blocks))

# block size used by server (standard block size + encryption nonce + block ID identifier space)
complete_server_block_size = settings.blockSize + settings.encryption_nonce_length + client_block_encoding_length

# handler of tcp requests
class MyTCPHandler(socketserver.StreamRequestHandler):


    # receive command from client
    def handle(self):
        # read command
        command = self.rfile.readline().strip()

        # read block
        # print("Received command: " + str(command) )
        block = self.rfile.read(complete_server_block_size)
        # pprint("received block ")# + str(command))
        # send request to server class and retrieve a response
        response = server.handle_request(command, block)
        # just send back response
        if len(response) == complete_server_block_size:
            # pprint("send response: " + str(len(response)) + " bytes")
            self.request.sendall(response)
        elif len(response) > 0:
            pprint("ERROR: Response length: " + str(len(response)))
        else:
            # pprint("NO REPONSE")
            self.request.sendall(b'')


# class managing server 
class Server():
    

    # init server
    def __init__(self):

        # init TCP server
        if settings.skip_network_connection == False:
            handler = MyTCPHandler
            self.server = socketserver.TCPServer((settings.HOST, settings.PORT), handler)

    # start the TCP server
    def start(self):

        # start TCP server (keep running until interruption ctrl+C)
        self.server.serve_forever()

    # create empty database directory for settings system
    # this means that each block contains random bytes
    def create_database(self):
        # delete previous content in server dir
        # print("Del: " + str(settings.server_directory))
        shutil.rmtree(settings.server_directory)

        # recreate server dir and fill with blocks
        os.mkdir(settings.server_directory)
        for i in range(1, settings.N_blocks+1):
            # write empty block files as database
            # init_value = bytearray(secrets.token_bytes(complete_server_block_size))
            block_file = open(settings.server_directory + '/' + str(i), "bw")
            # block_file.write(init_value)
            block_file.close()
            # if i%10000 == 0:
            #     pprint("Written " + str(i) + " blocks")
        # print("initialised database with " + str(settings.N_blocks) + " blocks.")

    # handles request from server and returns result
    def handle_request(self, command, block):
        # pprint(command)
        command_indicator = chr(command[0])
        
        ### READ BLOCK
        if command_indicator == 'R':
            # get block ID from command
            block_id = (command[1:]).decode('utf-8')
            if not block_id.isnumeric():
                return bytes("block_id is not numeric")
            block_id = int(block_id)

            # print('Read ' + str(block_id))

            # handle read
            return self.handle_read(block_id)

        ### WRITE BLOCK
        elif command_indicator == 'W':
            # get block ID from command
            block_id = (command[1:]).decode('utf-8')
            if not block_id.isnumeric():
                return bytes("block_id is not numeric")
            block_id = int(block_id)

            # print('Write ' + str(block_id))
            
            # handle write
            return self.handle_write(block_id, block)
        # no proper command (yet)
        else:
            print(command)
            print(block)
            return bytes("No proper command", "utf-8")
        return ""

    # def __del__(self):
        # self.server.close()

    # read block from database
    def handle_read(self, block_id):
        # read block
        with open(settings.server_directory + '/' + str(block_id), "rb") as block_file:
            content = block_file.read()

        # invalid/empty block: create dummy value (0...)
        if len(content) < complete_server_block_size:
            content = b'0'*complete_server_block_size

        return content

    def handle_write(self, block_id, block):
        # read content to return after completion
        previous_content = self.handle_read(block_id)

        # write block
        with open(settings.server_directory + '/' + str(block_id), "wb") as block_file:
            block_file.write(block)

        return previous_content


if __name__ == "__main__":
    server = Server()
    server.create_database()
    server.start()
    