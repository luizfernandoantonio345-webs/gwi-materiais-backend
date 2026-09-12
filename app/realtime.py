import asyncio
import json

from fastapi import WebSocket


class GerenciadorConexoes:
    def __init__(self) -> None:
        self._conns: dict[WebSocket, str] = {}  # ws -> papel
        self._lock = asyncio.Lock()

    async def conectar(self, ws: WebSocket, papel: str) -> None:
        async with self._lock:
            self._conns[ws] = papel

    async def desconectar(self, ws: WebSocket) -> None:
        async with self._lock:
            self._conns.pop(ws, None)

    async def publicar(self, papeis: set[str], mensagem: dict) -> None:
        dados = json.dumps(mensagem)
        mortas = []
        for ws, papel in list(self._conns.items()):
            if papel in papeis:
                try:
                    await ws.send_text(dados)
                except Exception:
                    mortas.append(ws)
        if mortas:
            async with self._lock:
                for ws in mortas:
                    self._conns.pop(ws, None)


manager = GerenciadorConexoes()


async def publicar_evento(papeis, tipo: str, msg: str) -> None:
    """Broadcast best-effort — nunca deve quebrar a requisição que o chamou."""
    try:
        await manager.publicar(set(papeis), {"tipo": tipo, "msg": msg})
    except Exception:
        pass
