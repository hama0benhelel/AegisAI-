#!/usr/bin/env bash
set -euo pipefail
umask 077

pki_dir="$HOME/.local/share/aegisai-pki"
authority_dir="$pki_dir/authority"
gas_dir="$pki_dir/gas"

if [ -e "$gas_dir" ]; then
    echo "Dossier gaz déjà présent. Aucun certificat remplacé."
    exit 1
fi

test -f "$authority_dir/ca.key"
test -f "$authority_dir/ca.crt"

mkdir "$gas_dir"
chmod 755 "$gas_dir"

cat > "$authority_dir/gas.ext" <<'EOF'
basicConstraints=critical,CA:FALSE
keyUsage=critical,digitalSignature,keyEncipherment
extendedKeyUsage=serverAuth
subjectAltName=DNS:gas-agent
subjectKeyIdentifier=hash
authorityKeyIdentifier=keyid,issuer
EOF

openssl req -new -newkey rsa:2048 -nodes \
  -keyout "$gas_dir/key.pem" \
  -out "$authority_dir/gas.csr" \
  -subj "/CN=gas-agent"

openssl x509 -req \
  -in "$authority_dir/gas.csr" \
  -CA "$authority_dir/ca.crt" \
  -CAkey "$authority_dir/ca.key" \
  -set_serial 1004 \
  -out "$gas_dir/cert.pem" \
  -days 90 -sha256 \
  -extfile "$authority_dir/gas.ext"

cp "$authority_dir/ca.crt" "$gas_dir/ca.pem"
chmod 444 "$gas_dir/cert.pem" "$gas_dir/ca.pem"

openssl verify \
  -CAfile "$authority_dir/ca.crt" \
  -purpose sslserver "$gas_dir/cert.pem"

sudo chown 10001:10001 "$gas_dir/key.pem"
sudo chmod 400 "$gas_dir/key.pem"

echo "SUCCESS: certificat gaz créé et vérifié."
