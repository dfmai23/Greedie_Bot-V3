
import enum

class State(enum.Enum):
    STOPPED =   "Stopped"   # not playing anything
    PLAYING =   "Playing"   # playing music
    PAUSED  =   "Paused"    # paused
    #WAITING =   "Waiting"   # The player has finished its song but is still downloading the next one
    DONE    =   "Done"      # done playing current song

    def __str__(self):
        return self.name
#class State
