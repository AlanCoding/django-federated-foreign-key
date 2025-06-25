import json
from urllib.request import urlopen
from federated_foreign_key.fields import RemoteObject


class RemoteBook(RemoteObject):
    base_url = "http://localhost:8001/books/"

    def fetch(self):
        url = f"{self.base_url}{self.object_id}/"
        with urlopen(url) as response:
            return json.load(response)
