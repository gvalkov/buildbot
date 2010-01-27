# -*- test-case-name: buildbot.test.test_util -*-

from twisted.trial import unittest

from buildbot import util
from buildbot.util import deps


class Foo(util.ComparableMixin):
    compare_attrs = ["a", "b"]

    def __init__(self, a, b, c):
        self.a, self.b, self.c = a,b,c


class Bar(Foo, util.ComparableMixin):
    compare_attrs = ["b", "c"]

class Compare(unittest.TestCase):
    def testCompare(self):
        f1 = Foo(1, 2, 3)
        f2 = Foo(1, 2, 4)
        f3 = Foo(1, 3, 4)
        b1 = Bar(1, 2, 3)
        self.failUnless(f1 == f2)
        self.failIf(f1 == f3)
        self.failIf(f1 == b1)

class test_checkRepoURL(unittest.TestCase):
    def assertUrl(self, real_url, expected_url):
        new_url = util.remove_userpassword(real_url)
        self.assertEqual(expected_url, new_url)

    def test_url_with_no_user_and_password(self):
        self.assertUrl('http://myurl.com/myrepo', 'http://myurl.com/myrepo')
    
    def test_url_with_user_and_password(self):
        self.assertUrl('http://myuser:mypass@myurl.com/myrepo', 'http://myurl.com/myrepo')
    
    def test_another_url_with_no_user_and_password(self):
        self.assertUrl('http://myurl2.com/myrepo2', 'http://myurl2.com/myrepo2')
    
    def test_another_url_with_user_and_password(self):
        self.assertUrl('http://myuser2:mypass2@myurl2.com/myrepo2', 'http://myurl2.com/myrepo2')
    
    def test_with_different_protocol_without_user_and_password(self):
        self.assertUrl('ssh://myurl3.com/myrepo3', 'ssh://myurl3.com/myrepo3')
    
    def test_with_different_protocol_with_user_and_password(self):
        self.assertUrl('ssh://myuser3:mypass3@myurl3.com/myrepo3', 'ssh://myurl3.com/myrepo3')

    def test_file_path(self):
        self.assertUrl('/home/me/repos/my-repo', '/home/me/repos/my-repo')

    def test_win32file_path(self):
        self.assertUrl('c:\\repos\\my-repo', 'c:\\repos\\my-repo')


class testDependencies(unittest.TestCase):

    def test_walkDependencyDict(self):
        dep = {'A' : ['B', 'C'],
               'B' : ['D'],
               'C' : [],
               'D' : [],
              }

        walked = [['C', 'D'], 'B', 'A']
        walked_flat = ['C', 'D', 'B', 'A']

        res = deps.walkDependencyDict(dep)
        self.assertEqual(res, walked)

        res = deps.walkDependencyDict(dep, group_parallel=False)
        self.assertEqual(res, walked_flat)

    def test_getDependencies(self):

        dep = {'A' : ['B', 'D'],
               'B' : ['C', 'E'],
               'C' : ['D', 'E'],
               'D' : [],
               'E' : [],
               'F' : [],
               'G' : [],
              }

        res = deps.getDependencies('A', dep)
        walked = ['D', 'E', 'C', 'B', 'A']

        self.assertEqual(res, walked)
        self.assertEqual(deps.getDependencies('E', dep),
                         ['E'])

        dep['D'] = ['A']
        self.assertRaises(Exception,
                          deps.getDependencies, 'A', dep)
