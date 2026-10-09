#!/usr/bin/python
# snakeoil.py
# Chris X Edwards <snakeoil@xed.ch>
# Snake Oil is a Python library for interfacing with a TORCS
# race car simulator which has been patched with the server
# extentions used in the Simulated Car Racing competitions.
# http://scr.geccocompetitions.com/
#
# To use it, you must import it and create a "drive()" function.
# This will take care of option handling and server connecting, etc.
# To see how to write your own client do something like this which is
# a complete working client:
# /-----------------------------------------------\
# |#!/usr/bin/python                              |
# |import snakeoil                                |
# |if __name__ == "__main__":                     |
# |    C= snakeoil.Client()                       |
# |    for step in xrange(C.maxSteps,0,-1):       |
# |        C.get_servers_input()                  |
# |        snakeoil.drive_example(C)              |
# |        C.respond_to_server()                  |
# |    C.shutdown()                               |
# \-----------------------------------------------/
# This should then be a full featured client. The next step is to
# replace 'snakeoil.drive_example()' with your own. There is a
# dictionary which holds various option values (see `default_options`
# variable for all the details) but you probably only need a few
# things from it. Mainly the `trackname` and `stage` are important
# when developing a strategic bot.
#
# This dictionary also contains a ServerState object
# (key=S) and a DriverAction object (key=R for response). This allows
# you to get at all the information sent by the server and to easily
# formulate your reply. These objects contain a member dictionary "d"
# (for data dictionary) which contain key value pairs based on the
# server's syntax. Therefore, you can read the following:
#    angle, curLapTime, damage, distFromStart, distRaced, focus,
#    fuel, gear, lastLapTime, opponents, racePos, rpm,
#    speedX, speedY, speedZ, track, trackPos, wheelSpinVel, z
# The syntax specifically would be something like:
#    X= o[S.d['tracPos']]
# And you can set the following:
#    accel, brake, clutch, gear, steer, focus, meta
# The syntax is:
#     o[R.d['steer']]= X
# Note that it is 'steer' and not 'steering' as described in the manual!
# All values should be sensible for their type, including lists being lists.
# See the SCR manual or http://xed.ch/help/torcs.html for details.
#
# If you just run the snakeoil.py base library itself it will implement a
# serviceable client with a demonstration drive function that is
# sufficient for getting around most tracks.
# Try `snakeoil.py --help` to get started.

# for Python3-based torcs python robot client
import socket
import sys
import getopt
import os
import time
PI= 3.14159265359

data_size = 2**17

# Initialize help messages
ophelp=  'Options:\n'
ophelp+= ' --host, -H <host>    TORCS server host. [localhost]\n'
ophelp+= ' --port, -p <port>    TORCS port. [3001]\n'
ophelp+= ' --id, -i <id>        ID for server. [SCR]\n'
ophelp+= ' --steps, -m <#>      Maximum simulation steps. 1 sec ~ 50 steps. [100000]\n'
ophelp+= ' --episodes, -e <#>   Maximum learning episodes. [1]\n'
ophelp+= ' --track, -t <track>  Your name for this track. Used for learning. [unknown]\n'
ophelp+= ' --stage, -s <#>      0=warm up, 1=qualifying, 2=race, 3=unknown. [3]\n'
ophelp+= ' --debug, -d          Output full telemetry.\n'
ophelp+= ' --help, -h           Show this help.\n'
ophelp+= ' --version, -v        Show current version.'
usage= 'Usage: %s [ophelp [optargs]] \n' % sys.argv[0]
usage= usage + ophelp
version= "20130505-2"

def clip(v,lo,hi):
    if v<lo: return lo
    elif v>hi: return hi
    else: return v

def bargraph(x,mn,mx,w,c='X'):
    '''Draws a simple asciiart bar graph. Very handy for
    visualizing what's going on with the data.
    x= Value from sensor, mn= minimum plottable value,
    mx= maximum plottable value, w= width of plot in chars,
    c= the character to plot with.'''
    if not w: return '' # No width!
    if x<mn: x= mn      # Clip to bounds.
    if x>mx: x= mx      # Clip to bounds.
    tx= mx-mn # Total real units possible to show on graph.
    if tx<=0: return 'backwards' # Stupid bounds.
    upw= tx/float(w) # X Units per output char width.
    if upw<=0: return 'what?' # Don't let this happen.
    negpu, pospu, negnonpu, posnonpu= 0,0,0,0
    if mn < 0: # Then there is a negative part to graph.
        if x < 0: # And the plot is on the negative side.
            negpu= -x + min(0,mx)
            negnonpu= -mn + x
        else: # Plot is on pos. Neg side is empty.
            negnonpu= -mn + min(0,mx) # But still show some empty neg.
    if mx > 0: # There is a positive part to the graph
        if x > 0: # And the plot is on the positive side.
            pospu= x - max(0,mn)
            posnonpu= mx - x
        else: # Plot is on neg. Pos side is empty.
            posnonpu= mx - max(0,mn) # But still show some empty pos.
    nnc= int(negnonpu/upw)*'-'
    npc= int(negpu/upw)*c
    ppc= int(pospu/upw)*c
    pnc= int(posnonpu/upw)*'_'
    return '[%s]' % (nnc+npc+ppc+pnc)

class Client():
    def __init__(self,H=None,p=None,i=None,e=None,t=None,s=None,d=None,vision=False):
        # If you don't like the option defaults,  change them here.
        self.vision = vision

        self.host= 'localhost'
        self.port= 3001
        self.sid= 'SCR'
        self.maxEpisodes=1 # "Maximum number of learning episodes to perform"
        self.trackname= 'unknown'
        self.stage= 3 # 0=Warm-up, 1=Qualifying 2=Race, 3=unknown <Default=3>
        self.debug= False
        self.maxSteps= 100000  # 50steps/second
        self.parse_the_command_line()
        if H: self.host= H
        if p: self.port= p
        if i: self.sid= i
        if e: self.maxEpisodes= e
        if t: self.trackname= t
        if s: self.stage= s
        if d: self.debug= d
        self.S= ServerState()
        self.R= DriverAction()
        self.setup_connection()

    def setup_connection(self):
        # == Set Up UDP Socket ==
        try:
            self.so= socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        except socket.error as emsg:
            print('Error: Could not create socket...')
            sys.exit(-1)
        # == Initialize Connection To Server ==
        self.so.settimeout(1)

        n_fail = 5
        while True:
            # This string establishes track sensor angles! You can customize them.
            #a= "-90 -75 -60 -45 -30 -20 -15 -10 -5 0 5 10 15 20 30 45 60 75 90"
            # xed- Going to try something a bit more aggressive...
            a= "-45 -19 -12 -7 -4 -2.5 -1.7 -1 -.5 0 .5 1 1.7 2.5 4 7 12 19 45"

            initmsg='%s(init %s)' % (self.sid,a)

            try:
                self.so.sendto(initmsg.encode(), (self.host, self.port))
            except socket.error as emsg:
                sys.exit(-1)
            sockdata= str()
            try:
                sockdata,addr= self.so.recvfrom(data_size)
                sockdata = sockdata.decode('utf-8')
            except socket.error as emsg:
                print("Waiting for server on %d............" % self.port)
                print("Count Down : " + str(n_fail))
                if n_fail < 0:
                    print("relaunch torcs")
                    os.system('pkill torcs')
                    time.sleep(1.0)
                    if self.vision is False:
                        os.system('torcs -nofuel -nodamage -nolaptime &')
                    else:
                        os.system('torcs -nofuel -nodamage -nolaptime -vision &')

                    time.sleep(1.0)
                    os.system('sh autostart.sh')
                    n_fail = 5
                n_fail -= 1

            identify = '***identified***'
            if identify in sockdata:
                print("Client connected on %d.............." % self.port)
                break

    def parse_the_command_line(self):
        try:
            (opts, args) = getopt.getopt(sys.argv[1:], 'H:p:i:m:e:t:s:dhv',
                       ['host=','port=','id=','steps=',
                        'episodes=','track=','stage=',
                        'debug','help','version'])
        except getopt.error as why:
            print('getopt error: %s\n%s' % (why, usage))
            sys.exit(-1)
        try:
            for opt in opts:
                if opt[0] == '-h' or opt[0] == '--help':
                    print(usage)
                    sys.exit(0)
                if opt[0] == '-d' or opt[0] == '--debug':
                    self.debug= True
                if opt[0] == '-H' or opt[0] == '--host':
                    self.host= opt[1]
                if opt[0] == '-i' or opt[0] == '--id':
                    self.sid= opt[1]
                if opt[0] == '-t' or opt[0] == '--track':
                    self.trackname= opt[1]
                if opt[0] == '-s' or opt[0] == '--stage':
                    self.stage= int(opt[1])
                ######### REQUIRED FOR RACE MODE - DO NOT CHANGE OR REMOVE #########
                if opt[0] == '-p' or opt[0] == '--port':
                    self.port= int(opt[1])
                ######## END OF REQUIRED #########
                if opt[0] == '-e' or opt[0] == '--episodes':
                    self.maxEpisodes= int(opt[1])
                if opt[0] == '-m' or opt[0] == '--steps':
                    self.maxSteps= int(opt[1])
                if opt[0] == '-v' or opt[0] == '--version':
                    print('%s %s' % (sys.argv[0], version))
                    sys.exit(0)
        except ValueError as why:
            print('Bad parameter \'%s\' for option %s: %s\n%s' % (
                                       opt[1], opt[0], why, usage))
            sys.exit(-1)
        if len(args) > 0:
            print('Superflous input? %s\n%s' % (', '.join(args), usage))
            sys.exit(-1)

    ######### REQUIRED FOR RACE MODE - DO NOT CHANGE OR REMOVE #########
    def get_servers_input(self):
        '''Server's input is stored in a ServerState object'''
        if not self.so: return
        sockdata= str()

        while True:
            try:
                # Receive server data
                sockdata,addr= self.so.recvfrom(data_size)
                sockdata = sockdata.decode('utf-8')
            except socket.error as emsg:
                print('.', end=' ')
                #print "Waiting for data on %d.............." % self.port
            if '***identified***' in sockdata:
                print("Client connected on %d.............." % self.port)
                continue
            elif '***shutdown***' in sockdata:
                print((("Server has stopped the race on %d. "+
                        "You were in %d place.") %
                        (self.port,self.S.d['racePos'])))
                self.shutdown()
                return
            elif '***restart***' in sockdata:
                # What do I do here?
                print("Server has restarted the race on %d." % self.port)
                # I haven't actually caught the server doing this.
                self.shutdown()
                return
            elif not sockdata: # Empty?
                continue       # Try again.
            else:
                self.S.parse_server_str(sockdata)
                if self.debug:
                    sys.stderr.write("\x1b[2J\x1b[H") # Clear for steady output.
                    print(self.S)
                break # Can now return from this function.
    ########## END OF REQUIRED #########

    def respond_to_server(self):
        if not self.so: return
        try:
            message = repr(self.R)
            self.so.sendto(message.encode(), (self.host, self.port))
        except socket.error as emsg:
            print("Error sending to server: %s Message %s" % (emsg[1],str(emsg[0])))
            sys.exit(-1)
        if self.debug: print(self.R.fancyout())
        # Or use this for plain output:
        #if self.debug: print self.R

    def shutdown(self):
        if not self.so: return
        print(("Race terminated or %d steps elapsed. Shutting down %d."
               % (self.maxSteps,self.port)))
        self.so.close()
        self.so = None
        #sys.exit() # No need for this really.

class ServerState():
    '''What the server is reporting right now.'''
    def __init__(self):
        self.servstr= str()
        self.d= dict()

    def parse_server_str(self, server_string):
        '''Parse the server string.'''
        self.servstr= server_string.strip()[:-1]
        sslisted= self.servstr.strip().lstrip('(').rstrip(')').split(')(')
        for i in sslisted:
            w= i.split(' ')
            self.d[w[0]]= destringify(w[1:])

    def __repr__(self):
        # Comment the next line for raw output:
        return self.fancyout()
        # -------------------------------------
        out= str()
        for k in sorted(self.d):
            strout= str(self.d[k])
            if type(self.d[k]) is list:
                strlist= [str(i) for i in self.d[k]]
                strout= ', '.join(strlist)
            out+= "%s: %s\n" % (k,strout)
        return out

    def fancyout(self):
        '''Specialty output for useful ServerState monitoring.'''
        out= str()
        sensors= [ # Select the ones you want in the order you want them.
        #'curLapTime',
        #'lastLapTime',
        'stucktimer',
        #'damage',
        #'focus',
        'fuel',
        #'gear',
        'distRaced',
        'distFromStart',
        #'racePos',
        'opponents',
        'wheelSpinVel',
        'z',
        'speedZ',
        'speedY',
        'speedX',
        'targetSpeed',
        'rpm',
        'skid',
        'slip',
        'track',
        'trackPos',
        'angle',
        ]

        #for k in sorted(self.d): # Use this to get all sensors.
        for k in sensors:
            if type(self.d.get(k)) is list: # Handle list type data.
                if k == 'track': # Nice display for track sensors.
                    strout= str()
                 #  for tsensor in self.d['track']:
                 #      if   tsensor >180: oc= '|'
                 #      elif tsensor > 80: oc= ';'
                 #      elif tsensor > 60: oc= ','
                 #      elif tsensor > 39: oc= '.'
                 #      #elif tsensor > 13: oc= chr(int(tsensor)+65-13)
                 #      elif tsensor > 13: oc= chr(int(tsensor)+97-13)
                 #      elif tsensor >  3: oc= chr(int(tsensor)+48-3)
                 #      else: oc= '_'
                 #      strout+= oc
                 #  strout= ' -> '+strout[:9] +' ' + strout[9] + ' ' + strout[10:]+' <-'
                    raw_tsens= ['%.1f'%x for x in self.d['track']]
                    strout+= ' '.join(raw_tsens[:9])+'_'+raw_tsens[9]+'_'+' '.join(raw_tsens[10:])
                elif k == 'opponents': # Nice display for opponent sensors.
                    strout= str()
                    for osensor in self.d['opponents']:
                        if   osensor >190: oc= '_'
                        elif osensor > 90: oc= '.'
                        elif osensor > 39: oc= chr(int(osensor/2)+97-19)
                        elif osensor > 13: oc= chr(int(osensor)+65-13)
                        elif osensor >  3: oc= chr(int(osensor)+48-3)
                        else: oc= '?'
                        strout+= oc
                    strout= ' -> '+strout[:18] + ' ' + strout[18:]+' <-'
                else:
                    strlist= [str(i) for i in self.d[k]]
                    strout= ', '.join(strlist)
            else: # Not a list type of value.
                if k == 'gear': # This is redundant now since it's part of RPM.
                    gs= '_._._._._._._._._'
                    p= int(self.d['gear']) * 2 + 2  # Position
                    l= '%d'%self.d['gear'] # Label
                    if l=='-1': l= 'R'
                    if l=='0':  l= 'N'
                    strout= gs[:p]+ '(%s)'%l + gs[p+3:]
                elif k == 'damage':
                    strout= '%6.0f %s' % (self.d[k], bargraph(self.d[k],0,10000,50,'~'))
                elif k == 'fuel':
                    strout= '%6.0f %s' % (self.d[k], bargraph(self.d[k],0,100,50,'f'))
                elif k == 'speedX':
                    cx= 'X'
                    if self.d[k]<0: cx= 'R'
                    strout= '%6.1f %s' % (self.d[k], bargraph(self.d[k],-30,300,50,cx))
                elif k == 'speedY': # This gets reversed for display to make sense.
                    strout= '%6.1f %s' % (self.d[k], bargraph(self.d[k]*-1,-25,25,50,'Y'))
                elif k == 'speedZ':
                    strout= '%6.1f %s' % (self.d[k], bargraph(self.d[k],-13,13,50,'Z'))
                elif k == 'z':
                    strout= '%6.3f %s' % (self.d[k], bargraph(self.d[k],.3,.5,50,'z'))
                elif k == 'trackPos': # This gets reversed for display to make sense.
                    cx='<'
                    if self.d[k]<0: cx= '>'
                    strout= '%6.3f %s' % (self.d[k], bargraph(self.d[k]*-1,-1,1,50,cx))
                elif k == 'stucktimer':
                    if self.d[k]:
                        strout= '%3d %s' % (self.d[k], bargraph(self.d[k],0,300,50,"'"))
                    else: strout= 'Not stuck!'
                elif k == 'rpm':
                    g= self.d['gear']
                    if g < 0:
                        g= 'R'
                    else:
                        g= '%1d'% g
                    strout= bargraph(self.d[k],0,10000,50,g)
                elif k == 'angle':
                    asyms= [
                          "  !  ", ".|'  ", "./'  ", "_.-  ", ".--  ", "..-  ",
                          "---  ", ".__  ", "-._  ", "'-.  ", "'\.  ", "'|.  ",
                          "  |  ", "  .|'", "  ./'", "  .-'", "  _.-", "  __.",
                          "  ---", "  --.", "  -._", "  -..", "  '\.", "  '|."  ]
                    rad= self.d[k]
                    deg= int(rad*180/PI)
                    symno= int(.5+ (rad+PI) / (PI/12) )
                    symno= symno % (len(asyms)-1)
                    strout= '%5.2f %3d (%s)' % (rad,deg,asyms[symno])
                elif k == 'skid': # A sensible interpretation of wheel spin.
                    frontwheelradpersec= self.d['wheelSpinVel'][0]
                    skid= 0
                    if frontwheelradpersec:
                        skid= .5555555555*self.d['speedX']/frontwheelradpersec - .66124
                    strout= bargraph(skid,-.05,.4,50,'*')
                elif k == 'slip': # A sensible interpretation of wheel spin.
                    frontwheelradpersec= self.d['wheelSpinVel'][0]
                    slip= 0
                    if frontwheelradpersec:
                        slip= ((self.d['wheelSpinVel'][2]+self.d['wheelSpinVel'][3]) -
                              (self.d['wheelSpinVel'][0]+self.d['wheelSpinVel'][1]))
                    strout= bargraph(slip,-5,150,50,'@')
                else:
                    strout= str(self.d[k])
            out+= "%s: %s\n" % (k,strout)
        return out

class DriverAction():
    '''What the driver is intending to do (i.e. send to the server).
    Composes something like this for the server:
    (accel 1)(brake 0)(gear 1)(steer 0)(clutch 0)(focus 0)(meta 0) or
    (accel 1)(brake 0)(gear 1)(steer 0)(clutch 0)(focus -90 -45 0 45 90)(meta 0)'''
    def __init__(self):
       self.actionstr= str()
       # "d" is for data dictionary.
       self.d= { 'accel':0.2,
                   'brake':0,
                  'clutch':0,
                    'gear':1,
                   'steer':0,
                   'focus':[-90,-45,0,45,90],
                    'meta':0
                    }

    def clip_to_limits(self):
        """There pretty much is never a reason to send the server
        something like (steer 9483.323). This comes up all the time
        and it's probably just more sensible to always clip it than to
        worry about when to. The "clip" command is still a snakeoil
        utility function, but it should be used only for non standard
        things or non obvious limits (limit the steering to the left,
        for example). For normal limits, simply don't worry about it."""
        self.d['steer']= clip(self.d['steer'], -1, 1)
        self.d['brake']= clip(self.d['brake'], 0, 1)
        self.d['accel']= clip(self.d['accel'], 0, 1)
        self.d['clutch']= clip(self.d['clutch'], 0, 1)
        if self.d['gear'] not in [-1, 0, 1, 2, 3, 4, 5, 6]:
            self.d['gear']= 0
        if self.d['meta'] not in [0,1]:
            self.d['meta']= 0
        if type(self.d['focus']) is not list or min(self.d['focus'])<-180 or max(self.d['focus'])>180:
            self.d['focus']= 0

    def __repr__(self):
        self.clip_to_limits()
        out= str()
        for k in self.d:
            out+= '('+k+' '
            v= self.d[k]
            if not type(v) is list:
                out+= '%.3f' % v
            else:
                out+= ' '.join([str(x) for x in v])
            out+= ')'
        return out
        return out+'\n'

    def fancyout(self):
        '''Specialty output for useful monitoring of bot's effectors.'''
        out= str()
        od= self.d.copy()
        od.pop('gear','') # Not interesting.
        od.pop('meta','') # Not interesting.
        od.pop('focus','') # Not interesting. Yet.
        for k in sorted(od):
            if k == 'clutch' or k == 'brake' or k == 'accel':
                strout=''
                strout= '%6.3f %s' % (od[k], bargraph(od[k],0,1,50,k[0].upper()))
            elif k == 'steer': # Reverse the graph to make sense.
                strout= '%6.3f %s' % (od[k], bargraph(od[k]*-1,-1,1,50,'S'))
            else:
                strout= str(od[k])
            out+= "%s: %s\n" % (k,strout)
        return out

# == Misc Utility Functions
def destringify(s):
    '''makes a string into a value or a list of strings into a list of
    values (if possible)'''
    if not s: return s
    if type(s) is str:
        try:
            return float(s)
        except ValueError:
            print("Could not find a value in %s" % s)
            return s
    elif type(s) is list:
        if len(s) < 2:
            return destringify(s[0])
        else:
            return [destringify(i) for i in s]

def drive_example(c):
    '''This is only an example. It will get around the track but the
    correct thing to do is write your own `drive()` function.'''
    S,R= c.S.d,c.R.d
    target_speed=300

    # Steer To Corner
    R['steer']= S['angle']*15 / PI
    # Steer To Center
    R['steer']-= S['trackPos']*.10

    # Throttle Control
    if S['speedX'] < target_speed - (R['steer']*50):
        R['accel']+= .01
    else:
        R['accel']-= .01
    if S['speedX']<10:
       R['accel']+= 1/(S['speedX']+.1)

    # Traction Control System
    if ((S['wheelSpinVel'][2]+S['wheelSpinVel'][3]) -
       (S['wheelSpinVel'][0]+S['wheelSpinVel'][1]) > 5):
       R['accel']-= .2

    # Automatic Transmission
    R['gear']=1
    if S['speedX']>50:
        R['gear']=2
    if S['speedX']>80:
        R['gear']=3
    if S['speedX']>110:
        R['gear']=4
    if S['speedX']>140:
        R['gear']=5
    if S['speedX']>170:
        R['gear']=6
    return


# ================ IMPROVED DRIVER (v7: v6 + no power-oversteer, no braking in a slide, gentler braking) ================
# TUNABLE SETTINGS - change ONE at a time, then re-run and compare lap time and damage.
MAX_SPEED       = 280    # km/h allowed on long straights
MIN_SPEED       = 60     # km/h allowed in the tightest corners
SPEED_PER_METRE = 1.2    # extra km/h allowed per metre of clear track ahead
BRAKE_GAIN      = 25.0   # bigger number = gentler braking
EDGE_LIMIT      = 0.85   # |trackPos| above this = near the track edge, so slow down
EDGE_SPEED      = 80     # km/h cap when near the track edge
STEER_LOCK_SLOW = 0.35   # steering 'stiffness' at low speed (smaller = steers harder)
STEER_LOCK_FAST = 0.90   # steering 'stiffness' at high speed (bigger = steers gentler)
CENTER_GAIN     = 0.40   # how strongly the car steers back toward the track middle
MISALIGN_LIMIT  = 0.8    # radians (~46 deg). Car pointing this far off the track direction = almost no throttle
CRAWL_THROTTLE  = 0.35   # NEW v4: minimum throttle share when sideways but slow, so it can turn around
BRAKE_STEER_CUT = 0.0    # v4: 0 = full braking while steering (v3's 0.4 made the downhill corner worse)
ACCEL_RAMP      = 0.08   # NEW v4: max throttle increase per step (smooth, stops 'too hard' acceleration)
OFFTRACK_ACCEL  = 0.30   # NEW v4: max throttle while off the track surface (|trackPos| > 1)
ENABLE_RECOVERY = True   # reverse out when truly stuck (set False to switch off)
STUCK_SPEED     = 3      # km/h: slower than this AND badly angled = stuck
STUCK_ANGLE     = 0.5236 # radians (30 deg)
STUCK_STEPS     = 100    # steps of 'stuck' before reversing
REVERSE_STEPS   = 60     # reverse for at most this many steps (stops early once the car is straight)
REVERSE_COOLDOWN= 150    # NEW v4: steps of forward driving before another reverse is allowed
LOG_TO_FILE     = True   # NEW v4: writes drive_log_HHMMSS.csv next to the script
LOG_EVERY       = 5      # log one row every N steps
STEER_RATE      = 0.15   # NEW v5: max steering change per step (damps the wobble out of corners)
EXIT_THROTTLE_CUT = 0.5  # v5: throttle limit at high speed = 1 - this * |steer|
LOW_SPEED_LIMIT = 110    # NEW v7: below this speed the car is in a low gear and its rear wheels spin up easily
LOW_SPEED_THROTTLE_CUT = 1.2  # NEW v7: below LOW_SPEED_LIMIT the throttle limit = 1 - this * |steer|
MIN_TURN_THROTTLE = 0.10 # NEW v7: never cut the throttle below this just because of steering
SLIDE_ANGLE     = 0.35   # NEW v7: car pointing this far (radians) off the track direction = it is sliding
SLIDE_BRAKE_MAX = 0.20   # NEW v7: maximum brake while sliding (lift off instead of stamping on it)
BRAKE_MAX       = 0.70   # NEW v7: maximum brake at any time
BRAKE_RAMP      = 0.15   # NEW v7: brake may rise by at most this much per step

# NEW v4: per-corner speed caps. Each entry is (start_metre, end_metre, max_kmh) measured
# from the start line (distFromStart). Start EMPTY, then fill in using the log file.
# Example:  SLOW_ZONES = [(2150, 2400, 90)]
# v6: values taken from your log files. In every lap the car reached the Corkscrew left bend at
# ~72 km/h WITH throttle, then the track turned hard right at 2476-2492 m and the car ran wide.
SLOW_ZONES = [(2395, 2515, 42)]   # brake on the straight before 2440 m, then hold ~42 km/h through the Corkscrew

# NEW v5: where on the track width to drive in a stretch. Each entry is
# (start_metre, end_metre, trackPos_target). trackPos: 0 = middle, +1 = left edge, -1 = right edge.
# Example (a corner where you want the car to hug the left side): LINE_POINTS = [(2200, 2300, 0.6)]
# v6: hug the inside of the left bend (+), then swing to the right side for the right-hand hairpin (-)
LINE_POINTS = [(2440, 2476, 0.4), (2476, 2515, -0.5)]

# v6: maximum throttle in a stretch (start_metre, end_metre, max_accel 0..1). No big throttle mid-corner.
ACCEL_ZONES = [(2440, 2492, 0.2)]

_state = {'stuck':0, 'rev_left':0, 'cooldown':0, 'prev_accel':0.0, 'prev_brake':0.0, 'step':0, 'log':None,
          'prev_steer':0.0, 'rev_sign':-1, 'rev_n':0, 'rev_a0':0.0, 'last100':-1}

def _log_row(S, R, mode):
    '''Write one CSV row now and then. Never allowed to crash the driver.'''
    if not LOG_TO_FILE: return
    try:
        if _state['log'] is None:
            import time
            _state['log']= open('drive_log_%s.csv' % time.strftime('%H%M%S'), 'w')
            _state['log'].write('step,dist,speed,angle,trackPos,damage,accel,brake,steer,gear,mode\n')
        if _state['step'] % LOG_EVERY == 0:
            _state['log'].write('%d,%.1f,%.1f,%.2f,%.2f,%d,%.2f,%.2f,%.2f,%d,%s\n' % (
                _state['step'], S['distFromStart'], S['speedX'], S['angle'], S['trackPos'],
                S['damage'], R['accel'], R['brake'], R['steer'], R['gear'], mode))
            _state['log'].flush()
    except Exception:
        pass

def drive_improved(c):
    '''v4: corner-aware speed (v1), speed-sensitive steering (v2), stability (v3),
    plus gentler recovery, per-corner speed zones, smooth throttle and a data log.'''
    S,R= c.S.d, c.R.d
    _state['step']+= 1
    speed= S['speedX']
    angle= S['angle']
    pos= S['trackPos']

    # --- Steering: speed-sensitive, with a pull back to the middle (v2) ---
    t= clip((speed-60)/140.0, 0, 1)
    lock= STEER_LOCK_SLOW + t*(STEER_LOCK_FAST-STEER_LOCK_SLOW)
    line= 0.0
    for (l_start, l_end, l_pos) in LINE_POINTS:      # NEW v5: aim for a chosen part of the track width
        if l_start <= S['distFromStart'] <= l_end:
            line= l_pos
    steer= (angle - (pos - line)*CENTER_GAIN) / lock
    steer= clip(steer, -1, 1)
    steer= clip(steer, _state['prev_steer']-STEER_RATE, _state['prev_steer']+STEER_RATE)   # NEW v5
    _state['prev_steer']= steer
    R['steer']= steer

    # Print the distance every 100 m so you can read off where a corner is (NEW v5)
    d100= int(S['distFromStart'] // 100)
    if d100 != _state['last100']:
        _state['last100']= d100
        print('  [track position] %d m' % (d100*100))

    # --- Recovery (v4): reverse only briefly, then drive forward again ---
    if ENABLE_RECOVERY:
        if _state['rev_left'] > 0:
            _state['rev_left']-= 1
            _state['rev_n']+= 1
            # Self-check: if reversing makes the car point MORE the wrong way, flip the steering direction.
            if _state['rev_n'] == 15 and abs(angle) > _state['rev_a0'] + 0.1:
                _state['rev_sign']*= -1
            if _state['rev_n'] > 8 and abs(angle) < 0.35:   # straight enough: stop reversing
                _state['rev_left']= 0
            if _state['rev_left'] == 0:
                _state['cooldown']= REVERSE_COOLDOWN
            R['steer']= clip(_state['rev_sign'] * angle / 0.785398, -1, 1)
            _state['prev_steer']= R['steer']
            R['gear']= -1
            R['accel']= 0.3 if speed > -15 else 0
            R['brake']= 0
            _state['prev_accel']= 0.0
            _state['prev_brake']= 0.0
            _log_row(S, R, 'REVERSE')
            return
        if _state['cooldown'] > 0:
            _state['cooldown']-= 1
        if abs(speed) < STUCK_SPEED and abs(angle) > STUCK_ANGLE:
            _state['stuck']+= 1
        else:
            _state['stuck']= 0
        if _state['stuck'] > STUCK_STEPS and _state['cooldown'] == 0:
            _state['rev_left']= REVERSE_STEPS
            _state['rev_n']= 0
            _state['rev_a0']= abs(angle)
            _state['stuck']= 0

    # --- Target speed from the clear road ahead (v1) ---
    ahead= max(S['track'][9], 0)
    target_speed= clip(MIN_SPEED + ahead*SPEED_PER_METRE, MIN_SPEED, MAX_SPEED)
    if abs(pos) > EDGE_LIMIT:
        target_speed= min(target_speed, EDGE_SPEED)
    if abs(pos) > 1.0:                      # NEW v4: off the track surface, so crawl back
        target_speed= min(target_speed, 50)
    if abs(angle) > 0.6:                    # sideways: crawl until straight
        target_speed= min(target_speed, 40)
    for (z_start, z_end, z_speed) in SLOW_ZONES:   # NEW v4: per-corner caps
        if z_start <= S['distFromStart'] <= z_end:
            target_speed= min(target_speed, z_speed)

    # --- Throttle and brake ---
    err= target_speed - speed
    if err >= 0:
        R['accel']= clip(err/20.0, 0, 1)
        R['brake']= 0
    elif err > -3:
        R['accel']= 0
        R['brake']= 0
    else:
        R['accel']= 0
        R['brake']= clip(-err/BRAKE_GAIN, 0, 1)

    # Sideways = less throttle, BUT keep a crawl so the car can still turn itself around (v4)
    share= clip(1 - abs(angle)/MISALIGN_LIMIT, 0, 1)
    if speed < 25:
        share= max(share, CRAWL_THROTTLE)
    R['accel']*= share
    sliding= abs(angle) > SLIDE_ANGLE
    if not sliding:                         # NEW v7: limit throttle while steering (stops power-oversteer spins)
        cut= LOW_SPEED_THROTTLE_CUT if speed < LOW_SPEED_LIMIT else EXIT_THROTTLE_CUT
        R['accel']= min(R['accel'], max(1 - cut*abs(R['steer']), MIN_TURN_THROTTLE))
    if abs(pos) > 1.0:
        R['accel']= min(R['accel'], OFFTRACK_ACCEL)
    R['brake']*= max(1 - BRAKE_STEER_CUT*abs(clip(R['steer'], -1, 1)), 0.5)
    if sliding and speed > 25:              # NEW v7: in a slide, lift off. Do not stamp on the brake.
        R['accel']= 0
        R['brake']= min(R['brake'], SLIDE_BRAKE_MAX)
    R['brake']= min(R['brake'], BRAKE_MAX)                          # NEW v7: gentler braking
    R['brake']= min(R['brake'], _state['prev_brake'] + BRAKE_RAMP)
    _state['prev_brake']= R['brake']

    # Traction Control System (unchanged)
    if ((S['wheelSpinVel'][2]+S['wheelSpinVel'][3]) -
       (S['wheelSpinVel'][0]+S['wheelSpinVel'][1]) > 5):
       R['accel']= max(R['accel']-.2, 0)

    for (a_start, a_end, a_max) in ACCEL_ZONES:       # NEW v6: limited throttle in chosen stretches
        if a_start <= S['distFromStart'] <= a_end:
            R['accel']= min(R['accel'], a_max)

    # Smooth throttle: it may rise only a little each step (v4)
    R['accel']= min(R['accel'], _state['prev_accel'] + ACCEL_RAMP)
    _state['prev_accel']= R['accel']

    # Automatic Transmission (unchanged)
    R['gear']=1
    if speed>50:  R['gear']=2
    if speed>80:  R['gear']=3
    if speed>110: R['gear']=4
    if speed>140: R['gear']=5
    if speed>170: R['gear']=6
    _log_row(S, R, 'NORMAL')
    return

# ================ MAIN ================
if __name__ == "__main__":
    #### DO NOT HARCODE THE PORT
    C= Client()
    for step in range(C.maxSteps,0,-1):
        C.get_servers_input()
        drive_improved(C)
        C.respond_to_server()
    C.shutdown()
