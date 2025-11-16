# Bootstrap

From genesis to global:
1) Bring up Genesis Registry (private IP / tailnet).
2) Cloudflare Tunnel → private ingress for Workers/admins.
3) Launch first 10 VMs (VMKit).
4) Workers cache large artifacts; enable `/pcpu/jobs/*`.
5) Replicate in controlled waves; monitor gates.

See subfolders for scripts and templates.
