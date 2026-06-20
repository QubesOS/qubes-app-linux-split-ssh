# Qubes Split SSH

Split SSH keeps your SSH private keys in a separate, network-isolated vault
qube. Client qubes never see the keys: they reach a forwarded `ssh-agent`
socket over qrexec, and the qrexec policy in dom0 decides which client may
reach which agent. A compromised client can use a key for as long as the
policy allows, but it cannot read or copy the key itself.

Setup is automated by the `qubesos.setup.split_ssh` Ansible role.
