#!/usr/bin/env python

# references:
# http://www.retards.org/terminals/vt102.html
# http://vt100.net/docs/vt102-ug/contents.html

import FSM
import copy

NUL = 0    # Fill character; ignored on input.
ENQ = 5    # Transmit answerback message.
BEL = 7    # Ring the bell.
BS  = 8    # Move cursor left.
HT  = 9    # Move cursor to next tab stop.
LF = 10    # Line feed.
VT = 11    # Same as LF.
FF = 12    # Same as LF.
CR = 13    # Move cursor to left margin or newline.
SO = 14    # Invoke G1 character set.
SI = 15    # Invoke G0 character set.
XON = 17   # Resume transmission.
XOFF = 19  # Halt transmission.
CAN = 24   # Cancel escape sequence.
SUB = 26   # Same as CAN.
ESC = 27   # Introduce a control sequence.
DEL = 127  # Fill character; ignored on input.
SPACE = chr(32) # Space or blank character.

def constrain (n, min, max):
    '''This returns n constrained to the min and max bounds.
    '''
    if n < min:
        return min
    if n > max:
        return max
    return n

def push_digit (input_symbol, state, stack):
    stack.append(input_symbol)
def build_digit (input_symbol, state, stack):
    s = stack.pop()
    s = s + input_symbol
    stack.append(s)
def accept (input_symbol, state, stack):
    if input_symbol=='H':
        c = stack.pop()
        r = stack.pop()
        print 'HOME (r,c) -> (%s, %s)' % (r,c)
    if input_symbol == 'D':
        n = stack.pop()
        print 'BACK (n) -> %s' % n
    if input_symbol == 'B':
        n = stack.pop()
        print 'DOWN (n) -> %s' % n
def default (input_symbol, state, stack):
    print 'UNDEFINED: %s, %s -- RESETTING' % (input_symbol, state)
    stack=[]


def Emit (fsm):
	screen = fsm.something[0]
	screen.write(fsm.input_symbol)
def StartNumber (fsm):
	fsm.something.append (fsm.input_symbol)
def BuildNumber (fsm):
	ns = fsm.something.pop()
	ns = ns + fsm.input_symbol
	fsm.something.append (ns)
def DoBack (fsm):
	count = fsm.something.pop()
	screen = fsm.something[0]
	screen.cursor_back (count)
def DoDown (fsm):
	count = fsm.something.pop()
	screen = fsm.something[0]
	screen.cursor_down (count)
def DoForward (fsm):
	count = fsm.something.pop()
	screen = fsm.something[0]
	screen.cursor_forward (count)
def DoUp (fsm):
	count = fsm.something.pop()
	screen = fsm.something[0]
	screen.cursor_up (count)
def DoHome (fsm):
	c = fsm.something.pop()
	r = fsm.something.pop()
	screen = fsm.something[0]
	screen.cursor_home (r,c)
	pass

class term:
    '''This class encapsulates a generic terminal.
        It filters a stream and maintains the state of
        a screen object.
    '''
    def __init__ (self):
	self.screen = screen (24,80)
	self.stack = [self.screen]
        self.state = FSM ('INIT',stack)
	self.state.add_transition_any ('INIT', Emit, 'INIT')
	self.state.add_transition ('\x1b', 'INIT', None, 'ESC')
	self.state.add_transition_any ('ESC', None, 'INIT')
	self.state.add_transition ('[', 'ESC', None, 'ELB')
	self.state.add_transition_list (string.digits, 'ELB', StartNumber, 'NUMBER_1')
	self.state.add_transition_list (string.digits, 'NUMBER_1', BuildNumber, 'NUMBER_1')
	self.state.add_transition ('D', 'NUMBER_1', DoBack, 'INIT')
	self.state.add_transition ('B', 'NUMBER_1', DoDown, 'INIT')
	self.state.add_transition ('C', 'NUMBER_1', DoForward, 'INIT')
	self.state.add_transition ('A', 'NUMBER_1', DoUp, 'INIT')

	self.state.add_transition (';', 'NUMBER_1', None, 'SEMICOLON')
	self.state.add_transition_any ('SEMICOLON', None, 'INIT')
	self.state.add_transition_list (string.digits, 'SEMICOLON', StartNumber, 'NUMBER_2')
	self.state.add_transition_list (string.digits, 'NUMBER_2', BuildNumber, 'NUMBER_2')
	self.state.add_transition_any ('NUMBER_2', None, 'INIT')
	self.state.add_transition ('H', 'NUMBER_2', DoHome, 'INIT')
	self.state.add_transition ('f', 'NUMBER_2', DoHome, 'INIT')
    def test (self):
	dump = file('dump').read()
	for c in dump:
		self.state.process(c)
	print str(self.screen)

    old_crap = '''
        f.add_default_transition ('INIT', default)
        f.add_transition('INIT','\x1b', 'ESC', None)
        f.add_transition('ESC','[', 'ELB', None)
        f.add_transition_list('ELB',['0','1','2','3','4','5','6','7','8','9'], 'ELB_DIGIT', push_digit)
        f.add_transition_list('ELB_DIGIT',['0','1','2','3','4','5','6','7','8','9'], 'ELB_DIGIT', build_digit)
        f.add_transition('ELB_DIGIT',';', 'SEMICOLON', None)
        f.add_transition_list('SEMICOLON',['0','1','2','3','4','5','6','7','8','9'], 'ELB_DIGIT2', push_digit)
        f.add_transition_list('ELB_DIGIT2',['0','1','2','3','4','5','6','7','8','9'], 'ELB_DIGIT2', build_digit)
        f.add_transition_list('ELB_DIGIT2',['H','f'], 'INIT', accept)
        f.add_transition_list('ELB_DIGIT',['D','B','C','A'], 'INIT', accept)
    '''


class screen:
    def __init__ (self, r=24,c=80):
        self.rows = r
        self.cols = c
        self.cur_r = 1
        self.cur_c = 1
        self.scroll_row_start = 1
        self.scroll_row_end = self.rows
        self.mode_scape = 0
        self.w = [ [SPACE] * self.cols for c in range(self.rows)]

    def __str__ (self):
        s = ''
        for r in range (1, self.rows + 1):
            for c in range (1, self.cols + 1):
                s = s + self.get(r,c)
            s = s + '\n'
        return s

    def fill (self, ch=SPACE):
        self.fill_region (1,1,self.rows,self.cols, ch)

    def fill_region (self, rs,cs, re,ce, ch=SPACE):
        rs = constrain (rs, 1, self.rows)
        re = constrain (re, 1, self.rows)
        cs = constrain (cs, 1, self.cols)
        ce = constrain (ce, 1, self.cols)
        if rs > re:
            rs, re = re, rs
        if cs > ce:
            cs, ce = ce, cs
        for r in range (rs, re+1):
            for c in range (cs, ce + 1):
                self.put (r,c,ch)

    def write (self, ch):
        '''Puts a character at the current cursor position.
        cursor position if moved forward with wrap-around, but
        no scrolling is done if the cursor hits the lower-right corner
        of the screen.
        \r and \n both produce a call to crlf().
        '''
        if ch == '\r' or ch == '\n':
            self.crlf()
            return

        self.put(self.cur_r, self.cur_c, ch)
        old_r = self.cur_r
        old_c = self.cur_c
        self.cursor_forward()
        if old_c == self.cur_c:
            self.cursor_down()
            if old_r != self.cur_r:
                self.cursor_home (self.cur_r, 1)
            else:
                self.scroll_up ()
                self.cursor_home (self.cur_r, 1)
                self.erase_line()

    def crlf (self):
        '''This advances the cursor with CRLF properties.
        The cursor will line wrap and the screen may scroll.
        Under UNIX this is what happens when a chr(13) '\r' is read.
        '''
        self.cursor_home (self.cur_r, 1)
        old_r = self.cur_r
        self.cursor_down()
        if old_r == self.cur_r:
            self.scroll_up ()
            self.erase_line()

    def put (self, r, c, ch):
        '''Screen array starts at 1 index.'''
#        if r < 1 or r > self.rows or c < 1 or c > self.cols:
#            raise IndexError ('Screen array index out of range')
        ch = str(ch)[0]
        self.w[r-1][c-1] = ch

    def get (self, r, c):
        '''Screen array starts at 1 index.'''
#        if r < 1 or r > self.rows or c < 1 or c > self.cols:
#            raise IndexError ('Screen array index out of range')
        return self.w[r-1][c-1]

    def cursor_constrain (self):
        self.cur_r = constrain (self.cur_r, 1, self.rows)
        self.cur_c = constrain (self.cur_c, 1, self.cols)

    def cursor_home (self, r=1, c=1): # <ESC>[{ROW};{COLUMN}H
        self.cur_r = r
        self.cur_c = c
        self.cursor_constrain ()
    def cursor_back (self,count=1): # <ESC>[{COUNT}D (not confused with down)
        self.cur_r = self.cur_r - count
        self.cursor_constrain ()
    def cursor_down (self,count=1): # <ESC>[{COUNT}B (not confused with back)
        self.cur_r = self.cur_r + count
        self.cursor_constrain ()
    def cursor_forward (self,count=1): # <ESC>[{COUNT}C
        self.cur_c = self.cur_c + count
        self.cursor_constrain ()
    def cursor_up (self,count=1): # <ESC>[{COUNT}A
        self.cur_r = self.cur_r - count
        self.cursor_constrain ()
    def cursor_force_position (self, r, c): # <ESC>[{ROW};{COLUMN}f
        '''Identical to Cursor Home.'''
        self.cursor_home (r, c)
    def cursor_save (self): # <ESC>[s
        '''Save current cursor position.'''
        pass
    def cursor_unsave (self): # <ESC>[u
        '''Restores cursor position after a Save Cursor.'''
        pass
    def cursor_save_attrs (self): # <ESC>7
        '''Save current cursor position.'''
        pass
    def cursor_restore_attrs (self): # <ESC>8
        '''Restores cursor position after a Save Cursor.'''
        pass
    def scroll_constrain (self):
        '''This keeps the scroll region within the screen region.'''
        if self.scroll_row_start <= 0:
            self.scroll_row_start = 1
        if self.scroll_row_end > self.rows:
            self.scroll_row_end = self.rows
    def scroll_screen (self): # <ESC>[r
        '''Enable scrolling for entire display.'''
        self.scroll_row_start = 1
        self.scroll_row_end = self.rows
    def scroll_screen_rows (self, rs, re): # <ESC>[{start};{end}r
        '''Enable scrolling from row {start} to row {end}.'''
        self.scroll_row_start = rs
        self.scroll_row_end = re
        self.scroll_constrain()
    def scroll_down (self): # <ESC>D
        '''Scroll display down one line.'''
        # Screen is indexed from 1, but arrays are indexed from 0.
        s = self.scroll_row_start - 1
        e = self.scroll_row_end - 1
        self.w[s+1:e+1] = copy.deepcopy(self.w[s:e])
    def scroll_up (self): # <ESC>M
        '''Scroll display up one line.'''
        # Screen is indexed from 1, but arrays are indexed from 0.
        s = self.scroll_row_start - 1
        e = self.scroll_row_end - 1
        self.w[s:e] = copy.deepcopy(self.w[s+1:e+1])
    def erase_end_of_line (self): # <ESC>[K
        '''Erases from the current cursor position to
        the end of the current line.'''
        self.fill_region (self.cur_r, self.cur_c, self.cur_r, self.cols)
    def erase_start_of_line (self): # <ESC>[1K
        '''Erases from the current cursor position to
        the start of the current line.'''
        self.fill_region (self.cur_r, 1, self.cur_r, self.cur_c)
    def erase_line (self): # <ESC>[2K
        '''Erases the entire current line.'''
        self.fill_region (self.cur_r, 1, self.cur_r, self.cols)
    def erase_down (self): # <ESC>[J
        '''Erases the screen from the current line down to
        the bottom of the screen.'''
        self.erase_end_of_line ()
        self.fill_region (self.cur_r + 1, 1, self.rows, self.cols)
    def erase_up (self): # <ESC>[1J
        '''Erases the screen from the current line up to
        the top of the screen.'''
        self.erase_start_of_line ()
        self.fill_region (self.cur_r-1, 1, 1, self.cols)
    def erase_screen (self): # <ESC>[2J
        '''Erases the screen with the background color.'''
        self.fill ()

    def set_tab (self): # <ESC>H
        '''Sets a tab at the current position.'''
        pass
    def clear_tab (self): # <ESC>[g
        '''Clears tab at the current position.'''
        pass
    def clear_all_tabs (self): # <ESC>[3g
        '''Clears all tabs.'''
        pass

#        Insert line             Esc [ Pn L
#        Delete line             Esc [ Pn M
#        Delete character        Esc [ Pn P
#        Scrolling region        Esc [ Pn(top);Pn(bot) r


        
import tty, termios, sys

def getkey():
    file = sys.stdin.fileno()
    mode = termios.tcgetattr(file)
    try:
        tty.setraw(file, termios.TCSANOW)
        ch = sys.stdin.read(1)
    finally:
        termios.tcsetattr(file, termios.TCSANOW, mode)
    return ch

        
def test_typing ():
    s = screen (10,10)
    while 1:
        ch = getkey()
        s.type(ch)
        print str(s)
        print 

#import sys
#e = chr(0x1b)
#sys.stdout.write (e+'[6n')
#sys.stdout.write (e+'[c')
#sys.stdout.write (e+'[0c')
#sys.stdout.write (e+'[5;10r')
#sys.stdout.write (e+'[r')
#sys.stdout.write (e+'[5;10H')
#sys.stdout.write (e+'[K')
#sys.stdout.write (e+'[6n')
#for i in range (0,9):
#       sys.stdout.write (e + 'D')

#test_typing()
