import random

from locust import HttpUser, between, task

SENHA = "Gramo@Forte2026!"


class Almoxarife(HttpUser):
    wait_time = between(1, 3)

    def on_start(self):
        r = self.client.post("/auth/login", data={"username": "almoxarife@gramo.com", "password": SENHA})
        self.headers = {"Authorization": f"Bearer {r.json()['access_token']}"}

    @task(3)
    def listar_materiais(self):
        self.client.get("/materiais?limit=50", headers=self.headers, name="/materiais")

    @task(1)
    def buscar(self):
        termo = random.choice(["disco", "cabo", "luva", "fur"])
        self.client.get(f"/materiais?busca={termo}", headers=self.headers, name="/materiais?busca")

    @task(1)
    def meus_pedidos(self):
        self.client.get("/pedidos?limit=20", headers=self.headers, name="/pedidos")
