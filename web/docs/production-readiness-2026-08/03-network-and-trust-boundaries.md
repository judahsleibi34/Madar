# Network and trust boundaries

## Physical topology

```text
ISP/Internet
    |
router/NAT/firewall
    |
Ethernet switch
    |-- Node A (mail-focused target)
    |-- Node B (SaaS/AI target)
    `-- operator/client networks (not implicitly trusted)
```

Commissioning records router model/capabilities, switch model/managed status, both negotiated link speeds/duplex, IPv4/IPv6 addressing, MTU, DHCP reservations, DNS, and whether inter-VLAN filtering is actually supported.

## Minimal initial network

- Use DHCP reservations for stable addresses unless an operator-owned static-address plan exists outside the DHCP pool.
- One server LAN is acceptable initially only with default-deny host firewalls and Tailscale least-privilege policy.
- Expose no SaaS origin directly; Cloudflare tunnels terminate to loopback/container-local services.
- Preserve direct public mail NAT only for required mail protocols.
- Do not bridge Docker networks across nodes.

## Optional segmented target

If both switch and router support tagged VLANs and stateful inter-VLAN policy:

- management VLAN: operator devices and management interfaces;
- server VLAN: Node A/B workload interfaces;
- client/IoT VLANs: no unsolicited access to servers;
- optional backup VLAN only if it has real filtering and does not make an attached drive remotely deletable.

Avoid decorative VLANs if the router cannot enforce policy. Host firewalls and Tailscale remain mandatory.

## Required flows

| Source | Destination | Flow | Authentication/encryption |
|---|---|---|---|
| Cloudflare tunnel process | loopback SaaS origins | configured HTTP ports | tunnel identity; host-local plaintext |
| Internet mail peers | Node A | SMTP 25 | opportunistic TLS plus mail policy |
| mail users | Node A | submission/IMAPS; POP only if approved | TLS and mailbox auth |
| Node B backend/worker | Ollama gateway | dedicated HTTPS port | TLS certificate + bearer token + Tailscale grant |
| monitoring | both nodes/exporters | named ports | mTLS/token/Tailscale; no content |
| backup writer | backup destination | explicit transfer protocol | encrypted archive + transport auth |
| operators | both nodes | SSH | keys, IdP/Tailscale policy, host authorization |

All other east-west traffic is denied. LAN source address is not authentication.

## Tailscale policy model

Use grants, which current Tailscale documentation recommends for new policy. Tags apply only to non-human machines. Example intent—not ready-to-apply policy:

```text
group:infra-admin -> tag:node-a-mail,tag:node-b-app : tcp/22
tag:node-b-app -> tag:ollama-gateway : tcp/GATEWAY_PORT
tag:monitoring -> node exporter/app metric endpoints : exact ports
tag:backup-source -> backup receiver : exact port
deny by omission for all other pairs
```

Add policy tests for every allowed and denied flow before applying. Device approval is mandatory; evaluate tailnet lock. References retrieved 2026-08-19: [grants](https://tailscale.com/docs/features/access-control/grants), [tags](https://tailscale.com/docs/features/tags), and [security practices](https://tailscale.com/docs/reference/best-practices/security).

## Perimeter evidence procedure

Later root read-only capture:

```bash
sudo sshd -T
sudo ufw status verbose
sudo nft list ruleset
sudo iptables-save
sudo ip6tables-save
sudo iptables -S DOCKER-USER
sudo sysctl net.ipv4.ip_forward net.ipv6.conf.all.forwarding
sudo ss -lntup
```

From independent external IPv4 and IPv6 systems, scan only owned addresses and approved ports. Compare to the allowlist. Current Node A listeners requiring decisions: SSH 22; mail 25/465/587/110/143/993/995/4190; direct Mailcow web 8080/8443. SaaS origins are correctly loopback-bound.

## Lockout-safe firewall/SSH rollout

1. Physical console/remote-hands confirmed.
2. Export current effective rules/config and rollback commands.
3. Add new allow rules before removing old ones.
4. Test a second SSH session over IPv4, IPv6, and Tailscale as applicable.
5. Test required Docker-published and mail flows externally.
6. Remove obsolete rule; repeat tests.
7. Schedule automatic rollback only if it is tested and cannot create a wider exposure.

## Power and shared failure domains

UPS must cover Node A, Node B, router, and switch long enough for graceful database/mail shutdown. Size from measured watts, not PSU labels. Configure NUT or vendor tooling with staged warning and shutdown thresholds; only one authority issues shutdown. Test AC loss, low battery, restore, BIOS restart behavior, filesystem recovery, database crash recovery, and tunnel restart. Two machines behind one router/switch/outlet remain one site failure domain.
