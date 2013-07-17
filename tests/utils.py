#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free  Software Foundation; either version 2 of the License, or
# (at your option)  any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
# MA 02110-1301 USA.

import difflib
import os
import logging

import libvirt

import virtinst
import virtinst.cli
from virtinst import VirtualAudio
from virtinst import VirtualDisk
from virtinst import VirtualGraphics
from virtinst import VirtualVideoDevice

# pylint: disable=W0212
# Access to protected member, needed to unittest stuff

# Used to ensure consistent SDL xml output
os.environ["HOME"] = "/tmp"
os.environ["DISPLAY"] = ":3.4"

_cwd        = os.getcwd()
scratch     = os.path.join(_cwd, "tests", "testscratchdir")
_testuri    = "test:///%s/tests/testdriver.xml" % _cwd
_fakeuri    = "__virtinst_test__" + _testuri + ",predictable"
_remoteuri  = "__virtinst_test__" + _testuri + ",remote"
_kvmcaps    = "%s/tests/capabilities-xml/libvirt-0.7.6-qemu-caps.xml" % _cwd
_plainkvm   = "%s,qemu" % _fakeuri
_plainxen   = "%s,xen" % _fakeuri
_kvmuri     = "%s,caps=%s" % (_plainkvm, _kvmcaps)


def get_debug():
    return ("DEBUG_TESTS" in os.environ and
            os.environ["DEBUG_TESTS"] == "1")


def _make_uri(base, connver=None, libver=None):
    if connver:
        base += ",connver=%s" % connver
    if libver:
        base += ",libver=%s" % libver
    return base


def open_testdefault():
    return virtinst.cli.getConnection("test:///default")


def open_testdriver():
    return virtinst.cli.getConnection(_testuri)


def open_testkvmdriver():
    return virtinst.cli.getConnection(_kvmuri)


def open_plainkvm(connver=None, libver=None):
    return virtinst.cli.getConnection(_make_uri(_plainkvm, connver, libver))


def open_plainxen(connver=None, libver=None):
    return virtinst.cli.getConnection(_make_uri(_plainxen, connver, libver))


def open_test_remote():
    return virtinst.cli.getConnection(_remoteuri)

_default_conn = open_testdriver()
_conn = None


def set_conn(newconn):
    global _conn
    _conn = newconn


def reset_conn():
    set_conn(_default_conn)


def get_conn():
    return _conn
reset_conn()

# Register libvirt handler


def libvirt_callback(ignore, err):
    logging.warn("libvirt errmsg: %s", err[2])
libvirt.registerErrorHandler(f=libvirt_callback, ctx=None)


def sanitize_xml_for_define(xml):
    # Libvirt throws errors since we are defining domain
    # type='xen', when test driver can only handle type='test'
    # Sanitize the XML so we can define
    if not xml:
        return xml

    xml = xml.replace(">linux<", ">xen<")
    for t in ["xen", "qemu", "kvm"]:
        xml = xml.replace("<domain type=\"%s\">" % t,
                          "<domain type=\"test\">")
        xml = xml.replace("<domain type='%s'>" % t,
                          "<domain type='test'>")
    return xml


def test_create(testconn, xml):
    xml = sanitize_xml_for_define(xml)

    try:
        dom = testconn.defineXML(xml)
    except Exception, e:
        raise RuntimeError(str(e) + "\n" + xml)

    try:
        dom.create()
        dom.destroy()
        dom.undefine()
    except:
        try:
            dom.destroy()
        except:
            pass
        try:
            dom.undefine()
        except:
            pass


def read_file(filename):
    """Helper function to read a files contents and return them"""
    f = open(filename, "r")
    out = f.read()
    f.close()

    return out


def diff_compare(actual_out, filename=None, expect_out=None):
    """Compare passed string output to contents of filename"""
    if not expect_out:
        #file(filename, "w").write(actual_out)
        expect_out = read_file(filename)

    diff = "".join(difflib.unified_diff(expect_out.splitlines(1),
                                        actual_out.splitlines(1),
                                        fromfile=filename,
                                        tofile="Generated Output"))
    if diff:
        raise AssertionError("Conversion outputs did not match.\n%s" % diff)


def get_basic_paravirt_guest(installer=None):
    g = virtinst.Guest(_conn)
    g.type = "xen"
    g.name = "TestGuest"
    g.memory = int(200 * 1024)
    g.maxmemory = int(400 * 1024)
    g.uuid = "12345678-1234-1234-1234-123456789012"
    gdev = VirtualGraphics(_conn)
    gdev.type = "vnc"
    gdev.keymap = "ja"
    g.add_device(gdev)
    g.vcpus = 5

    if installer:
        g.installer = installer
    else:
        g.installer._install_kernel = "/boot/vmlinuz"
        g.installer._install_initrd = "/boot/initrd"

    g.installer._scratchdir = scratch
    g.add_default_input_device()
    g.add_default_console_device()

    return g


def get_basic_fullyvirt_guest(typ="xen", installer=None):
    g = virtinst.Guest(_conn)
    g.type = typ
    g.name = "TestGuest"
    g.memory = int(200 * 1024)
    g.maxmemory = int(400 * 1024)
    g.uuid = "12345678-1234-1234-1234-123456789012"
    g.cdrom = "/dev/loop0"
    gdev = VirtualGraphics(_conn)
    gdev.type = "sdl"
    g.add_device(gdev)
    g.features['pae'] = 0
    g.vcpus = 5
    if installer:
        g.installer = installer
    g.emulator = "/usr/lib/xen/bin/qemu-dm"
    g.installer.arch = "i686"
    g.installer.os_type = "hvm"

    g.installer._scratchdir = scratch
    g.add_default_input_device()
    g.add_default_console_device()

    return g


def make_import_installer(os_type="hvm"):
    inst = virtinst.ImportInstaller(_conn)
    inst.type = "xen"
    inst.os_type = os_type
    return inst


def make_distro_installer(location="/default-pool/default-vol", gtype="xen"):
    inst = virtinst.DistroInstaller(_conn)
    inst.type = gtype
    inst.os_type = "hvm"
    inst.location = location
    return inst


def make_live_installer(location="/dev/loop0", gtype="xen"):
    inst = virtinst.LiveCDInstaller(_conn)
    inst.type = gtype
    inst.os_type = "hvm"
    inst.location = location
    return inst


def make_pxe_installer(gtype="xen"):
    inst = virtinst.PXEInstaller(_conn)
    inst.type = gtype
    inst.os_type = "hvm"
    return inst


def build_win_kvm(path=None, fake=True):
    g = get_basic_fullyvirt_guest("kvm")
    g.os_type = "windows"
    g.os_variant = "winxp"
    g.add_device(get_filedisk(path, fake=fake))
    g.add_device(get_blkdisk())
    g.add_device(get_virtual_network())
    g.add_device(VirtualAudio(g.conn))
    g.add_device(VirtualVideoDevice(g.conn))

    return g


def get_floppy(path=None):
    if not path:
        path = "/default-pool/testvol1.img"
    d = VirtualDisk(_conn)
    d.path = path
    d.device = d.DEVICE_FLOPPY
    d.validate()
    return d


def get_filedisk(path=None, fake=True):
    if not path:
        path = "/tmp/test.img"
    d = VirtualDisk(_conn)
    d.path = path
    size = None
    if not fake:
        size = .000001
    d.set_create_storage(fake=fake, size=size)
    d.validate()
    return d


def get_blkdisk(path="/dev/loop0"):
    d = VirtualDisk(_conn)
    d.path = path
    d.validate()
    return d


def get_virtual_network():
    dev = virtinst.VirtualNetworkInterface(_conn)
    dev.macaddr = "22:22:33:44:55:66"
    dev.type = virtinst.VirtualNetworkInterface.TYPE_VIRTUAL
    dev.network = "default"
    return dev
