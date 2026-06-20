#
# The Qubes OS Project, http://www.qubes-os.org
#
# Copyright (C) 2026  Frederic Pierret <frederic@invisiblethingslab.com>
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
#
#

LIBDIR ?= /usr/lib

build:

install-vm-common:
	install -d $(DESTDIR)$(LIBDIR)/split-ssh
	install -m 0755 -t $(DESTDIR)$(LIBDIR)/split-ssh src/start-agent src/start-forwarder
	install -D -m 0755 src/split-ssh $(DESTDIR)/usr/bin/split-ssh
	install -D -m 0755 qubes-rpc/qubes.SshAgent $(DESTDIR)/etc/qubes-rpc/qubes.SshAgent
	install -D -m 0644 src/qubes-ssh.sh $(DESTDIR)/etc/profile.d/qubes-ssh.sh
	install -D -m 0644 systemd/split-ssh-agent@.service $(DESTDIR)$(LIBDIR)/systemd/system/split-ssh-agent@.service
	install -D -m 0644 systemd/split-ssh-forwarder@.service $(DESTDIR)$(LIBDIR)/systemd/system/split-ssh-forwarder@.service

install-vm-deb: install-vm-common
install-vm-fedora: install-vm-common
install-vm: install-vm-common

install-dom0:
	install -D -m 0644 qubes-rpc/qubes.SshAgent.policy $(DESTDIR)/etc/qubes/policy.d/90-qubes-split-ssh.policy

clean:
	rm -rf debian/changelog.*
	rm -rf pkgs
