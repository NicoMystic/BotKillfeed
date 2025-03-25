import socket
import struct
import time

def ping_dayz_server(ip, port, return_ping=False):
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(2)

        request = b"\xFF\xFF\xFF\xFFTSource Engine Query\x00"
        start_time = time.time()
        sock.sendto(request, (ip, port))
        data, _ = sock.recvfrom(4096)
        ping = round((time.time() - start_time) * 1000)  # Ping en ms
        sock.close()

        if data.startswith(b'\xFF\xFF\xFF\xFFI'):
            info = {}
            offset = 6

            def read_string():
                nonlocal offset
                end = data.index(b'\x00', offset)
                s = data[offset:end].decode('utf-8', errors='ignore')
                offset = end + 1
                return s

            info['name'] = read_string()
            read_string()  # Map (ignorée)
            read_string()  # Dossier (ignoré)
            read_string()  # Jeu (ignoré)
            offset += 2  # Skip app ID
            info['players'] = data[offset]
            offset += 1
            info['max_players'] = data[offset]

            message = f"🟢 **{info['name']}**\n👥 {info['players']}/{info['max_players']} joueurs connectés"

            if return_ping:
                return True, message, ping
            else:
                return True, message
        else:
            if return_ping:
                return False, "Réponse inconnue du serveur.", -1
            else:
                return False, "Réponse inconnue du serveur."
    except Exception as e:
        if return_ping:
            return False, f"🔴 Hors-ligne ou erreur : `{str(e)}`", -1
        else:
            return False, f"🔴 Hors-ligne ou erreur : `{str(e)}`"