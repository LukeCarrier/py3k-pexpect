#!/usr/bin/env python
import pexpect
import unittest
import commands

class ExpectTestCase(unittest.TestCase):
    #def runTest (self):
        
    def test_expect_exact (self):
        the_old_way = commands.getoutput('/bin/ls -l')

        p = pexpect.spawn('/bin/ls -l')
        try:
                the_new_way = ''
                while 1:
                        p.expect_exact ('\n')
                        the_new_way = the_new_way + p.before
        except:
                the_new_way = the_new_way[:-1]
                the_new_way = the_new_way.replace('\r','\n')

        assert the_old_way == the_new_way

    def test_expect (self):
        the_old_way = commands.getoutput('/bin/ls -l')

        p = pexpect.spawn('/bin/ls -l')
        try:
                the_new_way = ''
                while 1:
                        p.expect ('\n')
                        the_new_way = the_new_way + p.before
        except:
                the_new_way = the_new_way[:-1]
                the_new_way = the_new_way.replace('\r','\n')

        assert the_old_way == the_new_way

    def test_expect_eof (self):
        the_old_way = commands.getoutput('/bin/ls -l')

        p = pexpect.spawn('/bin/ls -l')
        p.expect_eof ()
        the_new_way = p.before
        the_new_way = the_new_way.replace('\r','')
        the_new_way = the_new_way[:-1]

        assert the_old_way == the_new_way


if __name__ == '__main__':
    unittest.main()

suite = unittest.makeSuite(ExpectTestCase,'test')

#fout = open('kill1','wb')
#fout.write(the_old_way)
#fout.close
#fout = open('kill2', 'wb')
#fout.write(the_new_way)
#fout.close

