#!/usr/bin/env bash
set -e

echo "---------------------------------------"
echo " Smart Mirror - RSA Key Generator"
echo "---------------------------------------"

# Create keys directory if missing
mkdir -p keys
cd keys

# Prevent accidental overwrite
if [ -f private.pem ]; then
  echo "❌ private.pem already exists! Aborting to avoid overwriting."
  exit 1
fi

echo "🔑 Generating RSA private key..."
openssl genrsa -out private.pem 2048
chmod 600 private.pem

echo "🔐 Generating RSA public key..."
openssl rsa -in private.pem -pubout -out public.pem

echo "---------------------------------------"
echo "✔ Keypair generated"
echo "  - keys/private.pem"
echo "  - keys/public.pem"
echo "---------------------------------------"

