import random

from vpn.piapy import PiaVpn


class VPNServerManager:
    def __init__(self):
        self.client = PiaVpn()
        self.regions = [
            "au-sydney",
            "au-brisbane",
            "au-adelaide",
            "au-melbourne",
            "au-australia-streaming-optimized",
            "au-perth",
            "new-zealand",
            "us-silicon-valley",
            "us-seattle",
            "us-west-streaming-optimized",
            "us-denver",
            "us-las-vegas",
            "us-west",
            "us-wyoming",
            "us-alaska",
            "us-montana",
            "us-new-mexico",
            "us-oklahoma",
            "us-arkansas",
            "us-mississippi",
            "us-north-dakota",
            "us-south-dakota",
            "us-oregon",
            "us-idaho",
            "us-missouri",
            "us-iowa",
            "us-indiana",
            "us-michigan",
            "us-chicago",
            "us-north-carolina",
            "us-tennessee",
            "us-wisconsin",
            "us-kansas",
            "us-louisiana",
            "us-virginia",
            "us-connecticut",
            "us-minnesota",
            "us-atlanta",
            "us-west-virginia",
            "us-rhode-island",
            "us-south-carolina",
            "us-ohio",
            "us-alabama",
            "us-vermont",
            "us-new-hampshire",
            "us-massachusetts",
            "us-maine",
            "us-washington-dc",
            "us-east",
            "us-florida",
            "us-new-york",
            "us-pennsylvania",
            "us-east-streaming-optimized",
            "ca-vancouver",
            "ca-ontario",
            "ca-montreal",
            "uk-london",
            "uk-streaming-optimized",
            "uk-manchester",
            "uk-southampton",
            "se-streaming-optimized",
            "se-stockholm",
            "it-milano",
        ]

    def connect_to_server(self):
        region = random.choice(self.regions)
        self.client.set_region(region)
        self.client.connect()

    def disconnect_from_server(self):
        self.client.disconnect()

    def rotate_server(self):
        self.disconnect_from_server()
        self.connect_to_server()
