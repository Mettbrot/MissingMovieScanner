from __future__ import unicode_literals

import sys
import xbmc
import xbmcgui
import xbmcplugin
import urllib
import json
import os
import time
import datetime
import xbmcaddon
from urlparse import parse_qs
from traceback import print_exc
import codecs

__settings__ = xbmcaddon.Addon(id='plugin.video.mms')
language = __settings__.getLocalizedString

LOG_ENABLED = False
handle = int(sys.argv[1])

# plugin modes
MODE_SCAN_SOURCE = 10
MODE_SHOW_SOURCES = 20
MODE_AUTO_TV_SOURCES = 30
MODE_AUTO_MOVIE_SOURCES = 40

# parameter keys
PARAMETER_KEY_MODE = b"mode"
PARAMETER_KEY_SOURCE = b"source"

# dir walker counters
dirCount = 0
fileCount = 0
filesFound = 0

#############################################################################################
# Functions
#############################################################################################

def log(line):
    xbmc.log(('[plugin.video.mms] ' + line).encode('utf-8', errors='ignore'),
             level=xbmc.LOGDEBUG)


def jsonrpc(query):
    return json.loads(xbmc.executeJSONRPC(json.dumps(query, encoding='utf-8')))


def clean_name(text):
    text = text.replace('%21', '!')
    text = text.replace('%3a', ':')
    text = text.replace('%5c', '\\')
    text = text.replace('%2f', '/')
    text = text.replace('%2c', ',')
    text = text.replace('%20', ' ')

    return text
    
def get_movie_sources():
    query = {
        "jsonrpc": "2.0",
        "method": "Files.GetSources",
        "params": {"media": "video"},
        "id": 1
    }
    shares = jsonrpc(query)

    shares = shares['result']
    shares = shares.get('sources')
    
    if(shares == None):
        shares = []
    
    results = []
    for s in shares:
        share_label = s['label']
        share_path = s['file']

        if share_path.startswith('addons://'):
            log("DROPPING SOURCE: " + share_label + " - " + share_path)
        elif share_path.startswith('multipath://'):
            share_path = share_path.replace('multipath://', '')
            parts = share_path.split('/')
            parts = [ clean_name(f) for f in parts ]

            for b in parts:
                if b:
                    share = {}
                    share['path'] = b
                    share['name'] = share_label
                    results.append(share)                

        else:
            share = {}
            share['path'] = share_path
            share['name'] = share_label
            results.append(share) 

    return results

def get_blacklist(blacklist_string):    
    log("Blacklist String : " + blacklist_string)
    bits = blacklist_string.split(",")
    blacklist = []
    for bit in bits:
        blackword = bit.strip().lower()
        if len(blackword) > 0:
            blacklist.append(blackword)
    return blacklist

def get_extensions(ext_string):
    log("Extension String : " + ext_string)
    bits = ext_string.split(",")
    extensions = []
    for bit in bits:
        ext = bit.strip().lower()
        extensions.append(ext)
    return extensions


def is_video_file(filename):
    name, ext = os.path.splitext(filename)
    return ext.lower() in FILE_EXTENSIONS


def is_blacklisted_file_type(filename):
    name, ext = os.path.splitext(filename)
    return ext.lower() in BLACKLISTED_EXTENSIONS


def file_contains_forbiden(filename):
    for blackword in BLACKLIST_STRINGS:
        if filename.lower().find(blackword.lower()) > -1:
            log(filename + " contains blacklisted string " + blackword)
            return True
            
    return False
    
def walk_Path(path, walked_files, progress):
    log("walk_Path(" + path + ")")
    
    if progress.iscanceled():
        return    
    
    global dirCount
    global fileCount
    global filesFound
    
    count_text = language(30105).format(str(dirCount), str(fileCount))
    found_text = language(30107).format(str(filesFound))
    progress.update(0, count_text, found_text, path)
    #time.sleep(5)
    
    # double slash the \ in the path
    path = path.replace("\\", "\\\\")
    query = {
        "jsonrpc": "2.0",
        "method": "Files.GetDirectory",
        "params": {"directory": path},
        "id": 1
    }
    set_files = jsonrpc(query)

    if(len(set_files) == 0):
        return
    
    if(set_files.get('error') != None):
        xbmcgui.Dialog().ok(language(30109), language(30110), str(set_files.get('error')))
        log("Error walking the source path: " + str(set_files.get('error')))
        return
    
    files = set_files['result']
    #['files']
    files = files.get('files')
    
    if(files == None):
        return
    
    dirCount += 1
    
    for file in files:
        if progress.iscanceled():
            return
        if file['filetype'] == "directory":
            walk_Path(file["file"], walked_files, progress)
        elif file['filetype'] == "file":
            fileCount += 1
            filename = file["file"]
            if is_video_file(filename) \
                    and not is_blacklisted_file_type(filename) \
                    and not file_contains_forbiden(filename):
                filesFound += 1
                log("WALKER ADDING FILE : " + filename)
                file_name = file["file"]
                #XBMC urlencodes the filename if it's in a .rar
                if file_name.startswith('rar://'):
                    file_name = urllib.unquote(file_name)
                walked_files.append(file_name)

def get_files(paths, progress):
    walked_files = []
    
    for path in paths:
        walk_Path(path, walked_files, progress)
    
    for file in walked_files:
        log("WALKED FILE : " + file)
        
    return walked_files

#############################################################################################
# Utility Functions
#############################################################################################

def addDirectoryItem(name, isFolder=True, parameters={}, totalItems=1):
    li = xbmcgui.ListItem(name)
    
    commands = []
    #commands.append(( "Info", "XBMC.Action(Info)", ))
    #commands.append(( "Scan", "XBMC.updatelibrary(video, '" + name + "')", ))
    #commands.append(( 'TEST', 'ActivateWindow(videolibrary, '" + name "')', ))
    #commands.append(( 'runme', 'XBMC.RunPlugin(plugin://video/myplugin)', ))
    #commands.append(( 'runother', 'XBMC.RunPlugin(plugin://video/otherplugin)', ))
    #commands.append(( "Scan", "ActivateWindow(videofiles, Movies)", ))#, '" + name + "')", ))
    li.addContextMenuItems(commands, replaceItems = True)

    # encode parameter values in utf-8 first
    utf8_params = dict(((key, unicode(value).encode('utf-8'))
                        for key, value in parameters.items()))

    url = sys.argv[0] + '?' + urllib.urlencode(utf8_params)

    if not isFolder:
        url = name
        
    log("Adding Directory Item: " + name + " totalItems:" + str(totalItems))
    
    #dirItem = DirectoryItem()
    
    return xbmcplugin.addDirectoryItem(handle=handle, url=url, listitem=li, isFolder=isFolder, totalItems=totalItems)

#############################################################################################
# UI Functions
#############################################################################################

def show_root_menu():

    addDirectoryItem(name=language(30111), parameters={ PARAMETER_KEY_MODE: MODE_AUTO_MOVIE_SOURCES }, isFolder=True)
    addDirectoryItem(name=language(30112), parameters={ PARAMETER_KEY_MODE: MODE_AUTO_TV_SOURCES }, isFolder=True)
    addDirectoryItem(name=language(30113), parameters={ PARAMETER_KEY_MODE: MODE_SHOW_SOURCES }, isFolder=True)
    xbmcplugin.endOfDirectory(handle=handle, succeeded=True)
    
    
def get_library_files(type_of_scan):

    library_files = []
    media_files = []

    #Movies    
    if type_of_scan == 1 or type_of_scan == 0:
        query = {
            "jsonrpc": "2.0",
            "method": "VideoLibrary.GetMovies",
            "params": {"properties": ["file", "trailer"]},
            "id": 1
        }
        result = jsonrpc(query)
        movies = result['result']
        
        movies = movies.get('movies')
        
        if(movies == None):
            if type_of_scan == 1:
                xbmcgui.Dialog().ok(language(30114), language(30115))
            movies = []	
        
        for m in movies:
            media_files.append(m['file'])
            
            #try:
            #    trailer = m['trailer']
            #    if not trailer.startswith('http://'):
            #        media_files.append(clean_name(trailer))
            #except KeyError:
            #    pass        
	
	#TV Shows
    if type_of_scan == 2 or type_of_scan == 0:
        query = {
            "jsonrpc": "2.0",
            "method": "VideoLibrary.GetEpisodes",
            "params": {"properties": ["file"]},
            "id": 1
        }
        result = jsonrpc(query)
        tvshows = result['result']
        tvshows = tvshows.get('episodes')
        
        if(tvshows == None):
            if type_of_scan == 2:
                xbmcgui.Dialog().ok(language(30116), language(30117))
            tvshows = []	

        for t in tvshows:
            media_files.append(t['file'])

    # add files from trailers and sets
    for f in media_files:

        if f.startswith("videodb://"):
            query = {
                "jsonrpc": "2.0",
                "method": "Files.GetDirectory",
                "params": {"directory": f },
                "id": 1
            }
            set_files = jsonrpc(query)

            sub_files = []
            sub_trailers =  []

            for item in set_files['result']['files']:
                sub_files.append(clean_name(item['file']))
                try:
                    trailer = item['trailer']
                    if not trailer.startswith('http://'):
                        library_files.append(clean_name(trailer))
                except KeyError:
                    pass

            library_files.extend(sub_files)
            library_files.extend(sub_trailers)
        elif f.startswith('stack://'):
            f = f.replace('stack://', '')
            f = f.replace(',,', '<ACTUALCOMMER>')
            parts = f.split(' , ')

            #parts = [ clean_name(f) for f in parts ]

            for b in parts:
                b = b.replace('<ACTUALCOMMER>', ',')
                b = clean_name(b)
                library_files.append(b)
        else:
            library_files.append(clean_name(f))

    # all paths to lower case
    #library_files = [ file_name.lower() for file_name in library_files ]
    
    # make a set from the paths
    library_files = set(library_files)

    return library_files
    
def path_len_compare(item1, item2):
    return (len(item2) - len(item1))
    
def auto_detect_sources(library_files):
    source_paths = []
    
    sources = get_movie_sources()
    source_paths_pre_select = []
    
    for source in sources:
        source_paths_pre_select.append(source['path'])

    # sort the source paths from longest to shortest
    # this is so we hit our nested paths first
    source_paths_pre_select = sorted(source_paths_pre_select, cmp=path_len_compare)

    # now iterate the library to count our source path uses
    source_paths_count = {}
    
    for library_file in library_files:
        for source_path in source_paths_pre_select:
            if library_file.lower().startswith(source_path.lower()):
                source_paths_count[source_path] = 1
                break
    
    for sorce_usage in source_paths_count:
        source_paths.append(sorce_usage)
        log("Source Auto Detected : " + sorce_usage)
    
    return source_paths
    
    
def get_missing(MovieList, FileList):

    missing = []
    
    for file in FileList:
        found = False
        for libFile in MovieList:
            if file.lower() == libFile.lower():
                found = True
                break
                
        if found == False:
            missing.append(file)

    missing.sort()
    return missing
    
def scan_movie_source(source_path, type_of_scan):
    log("scan_movie_source(source_path) : " + source_path)
    
    xbmc.executebuiltin( "Dialog.Close(busydialog)" )
    
    progress = xbmcgui.DialogProgress()
    progress.create(language(30118), language(30119))
    progress.update(0, language(30120))

    #get library files
    library_files = get_library_files(type_of_scan)
    
    source_paths = []
    
    #work out the source paths we need to scan
    if type_of_scan == 0:
        # for type 0 just add the selected path
        source_paths.append(source_path)
    elif type_of_scan == 1 or type_of_scan == 2:
        # for auto scan try to extract the source paths to walk by searching the library media file
        # this requires at least one library file for a source path to work
        # it also tries to use the deepest source path when there are nested paths
        source_paths = auto_detect_sources(library_files)
        
    #walk source paths
    progress.update(0, language(30121))
    movie_files = set(get_files(source_paths, progress))
    progress.close()
    
    # check for missing items
    missing_count = 0
    log_active = False
    full_log_path = ''
    missing = []
    
    missing = get_missing(library_files, movie_files)

    if len(missing) > 0:
        #if not library_files.issuperset(movie_files):
        #log("Adding missing library items to list for souce path: " + source_path)
        #missing.extend(list(movie_files.difference(library_files)))

        #log the missing to the log file
        log_enabled = xbmcplugin.getSetting(handle, "custom_log_enabled").decode('utf-8')
        log_filename_path = xbmcplugin.getSetting(handle, "log_file_name").decode('utf-8')

        if log_enabled == 'true' and os.path.exists(log_filename_path) == False:
            xbmcgui.Dialog().ok(language(30122), language(30123))
        elif log_enabled == 'true':
            try:
                full_log_path = log_filename_path + "missing.txt"
                with codecs.open(full_log_path.encode('utf-8'), "a", encoding='utf-8') as file:
                    file.write("*********************************************************\n")
                    file.write("Missing Scan Results " + str(datetime.datetime.now().strftime("%Y-%m-%d %H:%M")) + "\n")
                    file.write("*********************************************************\n")
                    for movie_file in missing:
                        # get the end of the filename without the extension
                        if os.path.splitext(movie_file.lower())[0].endswith("trailer"):
                            log(movie_file + " is a trailer and will be ignored!")
                        else:
                            log("Adding missing item: " + movie_file)
                            file.write(movie_file + "\n")

                            missing_count += 1
                            addDirectoryItem(movie_file, isFolder=False, totalItems=len(missing))
                file.close()
            except IOError as e:
                xbmcgui.Dialog().ok(language(30122), language(30124).format(full_log_path, str(sys.exc_info()[1])))
    else:
        addDirectoryItem(language(30125), isFolder=False, totalItems=1)
    xbmcplugin.endOfDirectory(handle=handle, succeeded=True)
    
    global dirCount
    global fileCount
    global filesFound
    count_text = language(30106).format(str(dirCount), str(fileCount), str(filesFound))
    
    if log_active:
        xbmcgui.Dialog().ok(language(30126), count_text, language(30127).format(str(missing_count)), language(30128).format(full_log_path))
    else:
        xbmcgui.Dialog().ok(language(30126), count_text, language(30127).format(str(missing_count)))
    
def show_source_list():
    source_paths = get_movie_sources()
    
    for source_path in source_paths:
        source_test = source_path['name'] + " (" + source_path['path'] + ")"
        addDirectoryItem(clean_name(source_test), parameters={ PARAMETER_KEY_MODE: MODE_SCAN_SOURCE, PARAMETER_KEY_SOURCE: source_path['path'] }, isFolder=True, totalItems=len(source_paths))
        
    xbmcplugin.endOfDirectory(handle=handle, succeeded=True)

    
# set up all the variables
params = parse_qs(sys.argv[2].lstrip(b'?'))
mode = int(urllib.unquote_plus(params[PARAMETER_KEY_MODE][0])) if PARAMETER_KEY_MODE in params else 0
source = urllib.unquote_plus(params[PARAMETER_KEY_SOURCE][0]).decode('utf-8') if PARAMETER_KEY_SOURCE in params else ""
LOG_ENABLED = xbmcplugin.getSetting(handle, "custom_log_enabled").decode('utf-8') == "true"
log("Missing Logging : " + str(LOG_ENABLED))
FILE_EXTENSIONS = xbmc.getSupportedMedia('video').decode('utf-8').split('|')
BLACKLISTED_EXTENSIONS = xbmcplugin.getSetting(handle, "blacklisted_file_extensions").decode('utf-8').split('|')
BLACKLIST_STRINGS = get_blacklist(xbmcplugin.getSetting(handle, "blacklist").decode('utf-8'))


# Depending on the mode do stuff
if not sys.argv[2]:
    ok = show_root_menu()
elif mode == MODE_SCAN_SOURCE:
    ok = scan_movie_source(source, 0)
elif mode == MODE_AUTO_MOVIE_SOURCES:
    ok = scan_movie_source(source, 1)
elif mode == MODE_AUTO_TV_SOURCES:
    ok = scan_movie_source(source, 2)
elif mode == MODE_SHOW_SOURCES:
    ok = show_source_list()
