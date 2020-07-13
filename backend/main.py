import music
import server
import SocketServer
import strip
import sys
import threading
import time

if __name__ == '__main__':
    strip = strip.Strip()

    port = 8000
    if len(sys.argv) >= 2:
        port = int(sys.argv[1])
    myServer = server.Server(port, strip)

    musicVis = music.MusicVis(strip)

    serverThread = threading.Thread(target=myServer.run)
    stripThread = threading.Thread(target=strip.animate)
    musicThread = threading.Thread(target=musicVis.run)

    try:
        serverThread.start()
        stripThread.start()
        musicThread.start()
        while True:
            time.sleep(60)
    except:
        strip.kill()
        strip.clear_and_show()
        musicVis.kill()
        myServer.kill()
    
    stripThread.join()
    musicThread.join()
    serverThread.join()