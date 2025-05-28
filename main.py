import dns.resolver
from scapy.all import IP, TCP, sr1
import time
import requests


def create_dns_record(
    domain,
    record_type,
    ip,
    cloudflare_api_token,
    zone_id,
    proxied=False,
    priority=0,
    weight=5,
    port=25565,
):
    """
    创建新的 DNS 记录
    """
    url = f"https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records"
    headers = {
        "Authorization": f"Bearer {cloudflare_api_token}",
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
            "proxied": proxied,
        }
    else:
        data = {
            "type": record_type,
            "name": domain,
            "content": ip,
            "ttl": 1,
            "proxied": proxied,
        }

    try:
        response = requests.post(url, json=data, headers=headers)
        if response.status_code == 200:
            print(f"DNS 记录创建成功: {record_type}")
            return response.json().get("result", {}).get("id")
        else:
            print(f"创建 DNS 记录失败: {response.status_code}, {response.text}")
            return None
    except requests.exceptions.RequestException as e:
        print(f"创建 DNS 记录失败: {e}")
        return None


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
        elif "An identical record already exists." in response.text:
            print("已经存在相同的记录了QAQ")
        else:
            print(f"更新 DNS 记录失败: {response.status_code}, {response.text}")
    except requests.exceptions.RequestException as e:
        print(f"更新 DNS 记录失败: {e}")


def get_or_create_dns_record(
    domain, cloudflare_api_token, zone_id, record_type, ip, **kwargs
):
    """
    获取或创建 DNS 记录，确保SRV和A记录不会同时存在
    """
    # 检查A记录
    a_record_id, a_record_type = get_dns_record_id(
        domain, cloudflare_api_token, zone_id
    )
    # 检查SRV记录
    srv_domain = f"_minecraft._tcp.{domain}"
    srv_record_id, srv_record_type = get_dns_record_id(
        srv_domain, cloudflare_api_token, zone_id
    )

    # 删除现有记录
    if a_record_id and a_record_type == "A":
        delete_dns_record(a_record_id, cloudflare_api_token, zone_id)
    if srv_record_id and srv_record_type == "SRV":
        delete_dns_record(srv_record_id, cloudflare_api_token, zone_id)

    # 创建新记录
    if record_type == "SRV":
        new_record_id = create_dns_record(
            srv_domain, record_type, ip, cloudflare_api_token, zone_id, **kwargs
        )
    else:
        new_record_id = create_dns_record(
            domain, record_type, ip, cloudflare_api_token, zone_id, **kwargs
        )

    return new_record_id


def get_dns_record_id(domain, cloudflare_api_token, zone_id):
    """
    获取 DNS 记录 ID 和类型
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
        return None, None

    records = response.json().get("result", [])
    for record in records:
        if record["name"] == domain:
            return record["id"], record["type"]
    return None, None


def delete_dns_record(record_id, cloudflare_api_token, zone_id):
    """
    删除 DNS 记录
    """
    url = (
        f"https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records/{record_id}"
    )
    headers = {
        "Authorization": f"Bearer {cloudflare_api_token}",
        "Content-Type": "application/json",
    }

    try:
        response = requests.delete(url, headers=headers)
        if response.status_code == 200:
            print("DNS 记录删除成功")
            return True
        else:
            print(f"删除 DNS 记录失败: {response.status_code}, {response.text}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"删除 DNS 记录失败: {e}")
        return False


def dns_query(domain, record_type):
    try:
        answers = dns.resolver.resolve(domain, record_type)

        return [answer.to_text() for answer in answers]
    except dns.resolver.NoAnswer:
        return False
    except dns.resolver.NXDOMAIN:
        return False
    except Exception as e:
        print(f"错误: {e}")


def tcp_ping(ip, port, count=5):
    delays = []
    print(f"正在 ping {ip}...")
    for _ in range(count):
        packet = IP(dst=ip) / TCP(dport=port, flags="S")
        start_time = time.time()
        response = sr1(packet, timeout=2, verbose=0)
        if response:
            end_time = time.time()
            delay = (end_time - start_time) * 1000  # 转换为毫秒
            delays.append(delay)
            print(f"来自 {ip} 的回复: 时间={delay:.2f}ms")
        else:
            print(f"对 {ip} 的请求超时")
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
    delays = {}
    for domain in DOMAINS:
        answers = dns_query(domain, "A")
        if answers != False:
            access = "A"
            for answer in answers:
                ip = answer
                delay = tcp_ping(ip, 25565)
                delays[domain] = delay
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
                delays[domain] = delay
                if delay and delay < best_delay:
                    best_delay = delay
                    best_domain = domain
        else:
            print(f"错误: {domain} 未找到")
    print(", ".join([f"{domain}:{delay}ms" for domain, delay in delays.items()]))
    print(f"最佳域名: {best_domain} ({best_delay}ms)")
    if best_domain != "":
        if access == "A":
            # 获取最佳域名的IP地址
            best_ip = dns_query(best_domain, "A")[0]
            record_id = get_or_create_dns_record(
                DOMAIN, CLOUDFLARE_API_TOKEN, ZONE_ID, "A", best_ip
            )
        elif access == "SRV":
            record_id = get_or_create_dns_record(
                DOMAIN, CLOUDFLARE_API_TOKEN, ZONE_ID, "SRV", srv_domain, port=port
            )
        else:
            print("错误: 未知访问类型")

        if record_id:
            print(f"DNS 记录操作成功，记录ID: {record_id}")
        else:
            print("DNS 记录操作失败")
    else:
        print("错误: 未找到域名")


if __name__ == "__main__":
    DOMAINS = [
        "ranmc.cc",
        "b1.ranmc.cc",
        "b2.ranmc.cc",
        "b3.ranmc.cc",
        "b4.ranmc.cc",
        "b5.ranmc.cc",
    ]
    DOMAIN = "你要解析的域名"
    CLOUDFLARE_API_TOKEN = "cf的key"
    ZONE_ID = "域名区域id"  # 替换为你的 Zone ID
    # RECORD_ID = get_or_create_dns_record(DOMAIN, CLOUDFLARE_API_TOKEN, ZONE_ID)

    main()
