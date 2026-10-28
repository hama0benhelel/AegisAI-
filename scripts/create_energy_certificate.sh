#!/usr/bin/env bash
set -euo pipefail
umask 077

pki_dir="$HOME/.local/share/aegisai-pki"
authority_dir="$pki_dir/authority"
energy_dir="$pki_dir/energy"

if [ -e "$energy_dir" ]; then
    echo "Dossier énergie déjà présent. Aucun certificat remplacé."
    exit 1
fi

test -f "$authority_dir/ca.key"
test -f "$authority_dir/ca.crt"

mkdir "$energy_dir"
chmod 755 "$energy_dir"

cat > "$authority_dir/energy.ext" <<'EOF'
basicConstraints=critical,CA:FALSE
keyUsage=critical,digitalSignature,keyEncipherment
extendedKeyUsage=serverAuth
subjectAltName=DNS:energy-agent
subjectKeyIdentifier=hash
authorityKeyIdentifier=keyid,issuer
EOF

openssl req -new -newkey rsa:2048 -nodes \
  -keyout "$energy_dir/key.pem" \
  -out "$authority_dir/energy.csr" \
  -subj "/CN=energy-agent"

openssl x509 -req \
  -in "$authority_dir/energy.csr" \
  -CA "$authority_dir/ca.crt" \
  -CAkey "$authority_dir/ca.key" \
  -set_serial 1003 \
  -out "$energy_dir/cert.pem" \
  -days 90 -sha256 \
  -extfile "$authority_dir/energy.ext"

cp "$authority_dir/ca.crt" "$energy_dir/ca.pem"
chmod 444 "$energy_dir/cert.pem" "$energy_dir/ca.pem"

openssl verify \
  -CAfile "$authority_dir/ca.crt" \
  -purpose sslserver "$energy_dir/cert.pem"

sudo chown 10001:10001 "$energy_dir/key.pem"
sudo chmod 400 "$energy_dir/key.pem"

echo "SUCCESS: certificat énergie créé et vérifié."
