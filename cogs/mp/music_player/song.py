
class Song:
    def __init__(self, title, length, path, url, artist=''):
        self.title = title
        self.length = length
        self.path = path        #path as unique id
        self.url = url          #url also determines type, local or from url
        self.artist = artist    #if no url -> no artist mostly...

    def display(self):   #formats song chat printing, mainly checking if is a urlsong
        song_display = self.title
        if self.artist != '': #is local song and has artist
            try: song_display = song_display + ' - ' + self.artist
            except: pass
        return song_display

    def info(self):
        info = 'Title: ' + self.title + '\n'
        if self.artist != '':
            info += 'Artist: ' + self.artist + '\n'
        info += 'Length: ' + str(int(self.length)) + '\n'
        info += 'Path: ' + self.path + '\n'
        if self.url != None:
            info += 'URL: ' + self.url
        return info
        
#class Song
