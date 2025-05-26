import dns.resolver
from scapy.all import IP, TCP, sr1
import time
import requests


def update_cloudflare_dns(
    domain, record_type, ip, proxied=False, priority=0, weight=5, port=25565
):
    url = (
        f"https://api.cloudflare.com/client/v4/zones/{ZONE_ID}/dns_records/{RECORD_ID}"
    )
    headers = {
        "Authorization": f"Bearer {CLOUDFLARE_API_TOKEN}",
        "Content-Type": "application/json",
    }
    if record_type == "SRV":
        data = {
            "type": record_type,
            "name": domain,
            "data": {
                "priority": priority,
                "weight": weight,
                "port": port,
                "target": ip,
            },
            "ttl": 1,
            "proxied": proxied,  # 不启用 Cloudflare 代理
        }
    else:
        data = {
            "type": record_type,
            "name": domain,
            "content": ip,
            "ttl": 1,
            "proxied": proxied,  # 不启用 Cloudflare 代理
        }
    try:
        response = requests.put(url, json=data, headers=headers)
        if response.status_code == 200:
            return True
        else:
            print(f"更新 DNS 记录失败: {response.status_code}, {response.text}")
    except requests.exceptions.RequestException as e:
        print(f"更新 DNS 记录失败: {e}")


def get_or_create_dns_record(domain, cloudflare_api_token, zone_id):
    """
    获取 DNS 记录 ID，如果记录不存在则创建新的记录
    """
    # 获取现有 DNS 记录
    record_id = get_dns_record_id(domain, cloudflare_api_token, zone_id)
    if record_id:
        print(f"DNS 记录已存在，ID: {record_id}")
        return record_id

    # 创建新的 DNS 记录
    return create_dns_record(domain, cloudflare_api_token, zone_id)


def get_dns_record_id(domain, cloudflare_api_token, zone_id):
    """
    获取 DNS 记录 ID
    """
    headers = {
        "Authorization": f"Bearer {cloudflare_api_token}",
        "Content-Type": "application/json",
    }

    url = f"https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records"
    params = {"name": domain}

    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"请求失败: {e}")
        return None

    records = response.json().get("result", [])
    for record in records:
        if record["name"] == domain:
            return record["id"]
    return None


def create_dns_record(domain, cloudflare_api_token, zone_id):
    """
    创建新的 DNS 记录
    """
    headers = {
        "Authorization": f"Bearer {cloudflare_api_token}",
        "Content-Type": "application/json",
    }

    url = f"https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records"

    # 默认创建 A 记录，指向 1.1.1.1（可以根据需要修改）
    data = {
        "type": "A",
        "name": domain,
        "content": "1.1.1.1",
        "ttl": 120,
        "proxied": False,
    }

    try:
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"创建记录失败: {e}")
        return None

    result = response.json().get("result")
    if result:
        print(f"DNS 记录创建成功，ID: {result['id']}")
        return result["id"]
    else:
        print("创建记录失败")
        return None


def dns_query(domain, record_type):
    try:
        answers = dns.resolver.resolve(domain, record_type)

        return [answer.to_text() for answer in answers]
    except dns.resolver.NoAnswer:
        return False
    except dns.resolver.NXDOMAIN:
        return False
    except Exception as e:
        print(f"Error: {e}")


def tcp_ping(ip, port, count=5):
    delays = []
    print(f"Pinging {ip}...")
    for _ in range(count):
        packet = IP(dst=ip) / TCP(dport=port, flags="S")
        start_time = time.time()
        response = sr1(packet, timeout=2, verbose=0)
        if response:
            end_time = time.time()
            delay = (end_time - start_time) * 1000  # 转换为毫秒
            delays.append(delay)
            print(f"Reply from {ip}: time={delay:.2f}ms")
        else:
            print(f"Request timed out for {ip}")
    if delays:
        avg_delay = sum(delays) / len(delays)

        return float(f"{avg_delay:.2f}")
    else:
        return False


def main():
    # print(
    #     dns_query("ranmc.cc", "A"),
    #     dns_query(f"_minecraft._tcp.b2.ranmc.cc", "SRV"),
    #     dns_query(
    #         dns_query(f"_minecraft._tcp.b2.ranmc.cc", "SRV")[0].split(" ")[3], "A"
    #     ),
    # )

    port = 25565
    srv_domain = ""
    access = ""
    best_domain = ""
    best_delay = float("inf")
    for domain in DOMAINS:
        answers = dns_query(domain, "A")
        if answers != False:
            access = "A"
            for answer in answers:
                ip = answer
                delay = tcp_ping(ip, 25565)
                if delay and delay < best_delay:
                    best_delay = delay
                    best_domain = domain
        elif dns_query(f"_minecraft._tcp.{domain}", "SRV") != False:
            access = "SRV"
            answers = dns_query(f"_minecraft._tcp.{domain}", "SRV")
            for answer in answers:
                ip = dns_query(answers[0].split(" ")[3], "A")[0]
                srv_domain = answers[0].split(" ")[3]
                port = int(answers[0].split(" ")[2])
                delay = tcp_ping(ip, int(answers[0].split(" ")[2]))
                if delay and delay < best_delay:
                    best_delay = delay
                    best_domain = domain
        else:
            print(f"Error: {domain} not found")

    print(f"Best domain: {best_domain} ({best_delay}ms)")
    if best_domain != "":
        if access == "A":
            update_cloudflare_dns(DOMAIN, "A", best_domain)
        elif access == "SRV":
            update_cloudflare_dns(
                f"_minecraft._tcp.{DOMAIN}", "SRV", srv_domain, port=port
            )
        else:
            print("Error: Unknown access type")
    else:
        print("Error: No domain found")


if __name__ == "__main__":
    DOMAINS = [
        "ranmc.cc",
        "b1.ranmc.cc",
        "b2.ranmc.cc",
        "b3.ranmc.cc",
        "b4.ranmc.cc",
        "b5.ranmc.cc",
    ]
    DOMAIN = "example.com"
    CLOUDFLARE_API_TOKEN = "your_cloudflare_api_token"
    ZONE_ID = "your_zone_id"  # 替换为你的 Zone ID
    RECORD_ID = get_or_create_dns_record(DOMAIN, CLOUDFLARE_API_TOKEN, ZONE_ID)

    main()
