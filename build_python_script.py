#
# This script uses the Duffy node management api to get fresh machines to run
# your CI tests on. Once allocated you will be able to ssh into that machine
# as the root user and setup the environ
#
# XXX: You need to add your own api key below, and also set the right cmd= line 
#      needed to run the tests
#
# Please note, this is a basic script, there is no error handling and there are
# no real tests for any exceptions. Patches welcome!

import json, urllib, subprocess, sys

import os
import signal
import socket
import sys
import time
import urllib



url_base="http://admin.ci.centos.org:8080"
api= os.environ['APIKEY']

NODE_TYPE = {
    "c7_64" : {"arch":"x86_64", "ver":"7"},
}

def test_port(address, port):
    s = socket.socket()
    try:
        s.connect((address, port))
        return True
    except socket.error:
        return False


class CentOSCI:
    def __init__(self):
        pass
    def create_vm(self,vm_tmpl):
        get_node_url = "%s/Node/get?key=%s&ver=%s&arch=%s" % (BASE_URL, API_KEY, NODE_TYPE[vm_tmpl]["ver"], NODE_TYPE[vm_tmpl]["arch"])
        get_node_reponse = urllib.urlopen(get_node_url).read()
        try:
            get_node_result = json.loads(get_node_reponse)
        except Exception, e_json:
            print get_node_reponse
            return
        return (get_node_result['ssid'], get_node_result['hosts'][0])
        
    def ssh_run(self, ip_addr, cmd):
        return  subprocess.call("ssh -t -o StrictHostKeyChecking=no root@%s '%s'" % (ip_addr,cmd), shell=True)

    def scp_jenkins_workspace(self, ip_addr):
        return  subprocess.call("scp -r -o StrictHostKeyChecking=no %s root@%s:/root/ " % (os.environ['WORKSPACE'], ip_addr), shell=True)

    def terminate_vm(self, vm_id):
        terminate_node_url = "%s/Node/done?key=%s&ssid=%s" % (BASE_URL, API_KEY, vm_id)
        return urllib.urlopen(terminate_node_url).read()
    
if __name__ == '__main__':
    vm_type = sys.argv[1]
    
    if vm_type in NODE_TYPE.keys():
        ci = CentOSCI()
        try:
            vm_id, vm_ip = ci.create_vm(vm_tmpl = vm_type)
        except Exception, e_vm_create:
            print "Cannot create VM."
            sys.exit(-1)

        # SIGTERM handler [THIS IS UGLY]
        def sigterm_handler(signal, frame):
            print "Build terminated ..."
            ci.terminate_vm(vm_id)
            sys.exit(1)
        signal.signal(signal.SIGTERM, sigterm_handler)

        print 'Waiting for SSHD on %s ...' % (vm_ip,)
        timeout = time.time() + 60*40 # 20mn
        while True:
            time.sleep(30)
            if test_port(vm_ip, 22) or time.time() > timeout:
                break
        testsuite_cmds = [ 'cd /root/%s && git clone https://github.com/CentOS/sig-atomic-buildscripts.git && cd sig-atomic-buildscripts && git checkout downstream && bash -x ./build_ostree_components.sh' % os.path.basename(os.environ['WORKSPACE'])]
        out = 0
        try:
            print 'Copying the test suite ...'
            ci.scp_jenkins_workspace(vm_ip)
            print 'Running the test suite ...'
            for testsuite_cmd in testsuite_cmds:
                out = ci.ssh_run(ip_addr = vm_ip, cmd = testsuite_cmd)

        except Exception, e:
            print "Can't connect to the VM: %s" % str(e)

        finally:
            try:
                print "Terminating the VM ..."
                ci.terminate_vm(vm_id)
            except Exception, e2:
                print "Can't terminate the VM: %s" % str(e2)
        sys.exit(out)

    else:
        print 'Invalid VM type.'
        sys.exit(1)


