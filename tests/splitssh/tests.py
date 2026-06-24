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
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301,
# USA.
#
import time

import qubes.tests.extra


class SplitSSHBase(qubes.tests.extra.ExtraTestCase):
    agent = "work"

    def setUp(self):
        super(SplitSSHBase, self).setUp()
        self.backend, self.frontend = self.create_vms(["vault", "client"])

        self.backend.start()
        if self.backend.run("ls /etc/qubes-rpc/qubes.SshAgent", wait=True) != 0:
            self.skipTest("split-ssh not installed in the template")

        self.keydir = ".ssh/identities.d/{}".format(self.agent)
        self.key_comment = "{}-test".format(self.agent)
        p = self.backend.run(
            "mkdir -p -m 0700 {kd} && "
            "ssh-keygen -q -t ed25519 -N '' -C {c} "
            "-f {kd}/id_test".format(kd=self.keydir, c=self.key_comment),
            passio_popen=True,
            passio_stderr=True,
        )
        _, stderr = p.communicate()
        self.assertEqual(
            p.returncode, 0, "key generation failed: {}".format(stderr.decode())
        )

        if (
            self.backend.run(
                "systemctl start split-ssh-agent@{}.service".format(self.agent),
                user="root",
                wait=True,
            )
            != 0
        ):
            self.fail("failed to start split-ssh-agent@{}".format(self.agent))
        self.backend_sock = "/run/split-ssh/{}.sock".format(self.agent)
        self.wait_for_socket(self.backend, self.backend_sock)

        self.qrexec_policy(
            "qubes.SshAgent", self.frontend.name, self.backend.name
        )

        self.frontend.start()
        p = self.frontend.run(
            "tee /rw/config/split-ssh-vault", passio_popen=True, user="root"
        )
        p.communicate(self.backend.name.encode())

        if (
            self.frontend.run(
                "systemctl start split-ssh-forwarder@{}.service".format(
                    self.agent
                ),
                user="root",
                wait=True,
            )
            != 0
        ):
            self.fail(
                "failed to start split-ssh-forwarder@{}".format(self.agent)
            )
        self.frontend_sock = "$HOME/.split-ssh/{}.sock".format(self.agent)
        self.wait_for_socket(self.frontend, self.frontend_sock)

    def wait_for_socket(self, vm, path):
        for _ in range(120):
            if vm.run("test -S {}".format(path), wait=True) == 0:
                return
            time.sleep(0.5)
        self.fail("socket {} did not appear on {}".format(path, vm.name))

    def ssh_add(self, vm, sock, args):
        p = vm.run(
            "SSH_AUTH_SOCK={} ssh-add {}".format(sock, args),
            passio_popen=True,
            passio_stderr=True,
        )
        stdout, stderr = p.communicate()
        return p.returncode, stdout.decode(), stderr.decode()

    @staticmethod
    def fingerprint(ssh_add_l_output):
        # "256 SHA256:<base64> <comment> (ED25519)"
        return ssh_add_l_output.split()[1]


class TC_00_Direct(SplitSSHBase):
    def test_000_agent_holds_key(self):
        ret, out, err = self.ssh_add(self.backend, self.backend_sock, "-l")
        self.assertEqual(ret, 0, "ssh-add -l in vault failed: {}".format(err))
        self.assertIn(self.key_comment, out)
        self.assertIn("ED25519", out)

    def test_010_cli_list(self):
        ret = self.backend.run(
            "split-ssh list {}".format(self.agent), wait=True
        )
        self.assertEqual(ret, 0, "split-ssh list failed in the vault")

    def test_020_forwarded_list_matches_vault(self):
        ret, vault_out, err = self.ssh_add(
            self.backend, self.backend_sock, "-l"
        )
        self.assertEqual(ret, 0, "ssh-add -l in vault failed: {}".format(err))
        ret, client_out, err = self.ssh_add(
            self.frontend, self.frontend_sock, "-l"
        )
        self.assertEqual(
            ret, 0, "ssh-add -l over the forwarder failed: {}".format(err)
        )
        self.assertEqual(
            self.fingerprint(vault_out),
            self.fingerprint(client_out),
            "forwarded agent exposes a different key than the vault",
        )

    def test_030_forwarded_sign(self):
        # Pull the public key out of the agent over qrexec, then ask the agent
        # to actually sign and verify with it. This is the round-trip an
        # OpenSSH update is most likely to break.
        cmd = (
            "SSH_AUTH_SOCK={s} ssh-add -L > /tmp/agent.pub && "
            "SSH_AUTH_SOCK={s} ssh-add -T /tmp/agent.pub".format(
                s=self.frontend_sock
            )
        )
        p = self.frontend.run(cmd, passio_popen=True, passio_stderr=True)
        stdout, stderr = p.communicate()
        self.assertEqual(
            p.returncode,
            0,
            "agent sign/verify over qrexec failed: {}{}".format(
                stdout.decode(), stderr.decode()
            ),
        )

    def test_040_private_key_stays_in_vault(self):
        # The private key file exists only in the vault.
        in_vault = self.backend.run(
            "test -e $HOME/{}/id_test".format(self.keydir), wait=True
        )
        self.assertEqual(in_vault, 0, "private key missing from the vault")
        on_client = self.frontend.run(
            "test -e $HOME/.ssh/identities.d/{}/id_test".format(self.agent),
            wait=True,
        )
        self.assertNotEqual(
            on_client, 0, "private key file leaked onto the client"
        )

        # Over the forwarder only public key material is reachable: the agent
        # protocol has no request to export a private key.
        ret, listing, err = self.ssh_add(
            self.frontend, self.frontend_sock, "-L"
        )
        self.assertEqual(
            ret, 0, "ssh-add -L over the forwarder failed: {}".format(err)
        )
        self.assertNotIn("PRIVATE KEY", listing)
        self.assertTrue(
            listing.startswith("ssh-"),
            "forwarder returned non-public-key data: {}".format(listing),
        )

        # The exposed public key is exactly the vault key's public half, so the
        # client uses the vault key without ever holding the private part.
        p = self.backend.run(
            "cat $HOME/{}/id_test.pub".format(self.keydir),
            passio_popen=True,
            passio_stderr=True,
        )
        pub, err = p.communicate()
        self.assertEqual(
            p.returncode,
            0,
            "cannot read vault public key: {}".format(err.decode()),
        )
        self.assertEqual(
            pub.decode().split()[1],
            listing.split()[1],
            "forwarded public key does not match the vault key",
        )

    def test_050_cli_reload(self):
        ret = self.backend.run(
            "split-ssh reload {}".format(self.agent), wait=True
        )
        self.assertEqual(ret, 0, "split-ssh reload failed in the vault")
        ret, out, err = self.ssh_add(self.backend, self.backend_sock, "-l")
        self.assertEqual(
            ret, 0, "ssh-add -l after reload failed: {}".format(err)
        )
        self.assertIn(self.key_comment, out)

    def test_060_cli_add_passthrough(self):
        ret = self.backend.run(
            "ssh-keygen -q -t ed25519 -N '' -C dummy-test -f /tmp/dummy-key",
            wait=True,
        )
        self.assertEqual(ret, 0, "dummy key generation failed")
        ret = self.backend.run(
            "split-ssh add {} /tmp/dummy-key".format(self.agent), wait=True
        )
        self.assertEqual(ret, 0, "split-ssh add <key> failed")
        ret, out, err = self.ssh_add(self.backend, self.backend_sock, "-l")
        self.assertEqual(ret, 0, "ssh-add -l failed: {}".format(err))
        self.assertIn("dummy-test", out)
        self.assertIn(self.key_comment, out)

    def test_070_cli_rejects_bad_agent(self):
        ret = self.backend.run("split-ssh list ../etc", wait=True)
        self.assertNotEqual(ret, 0, "invalid agent name was not rejected")


def list_tests():
    return (TC_00_Direct,)
