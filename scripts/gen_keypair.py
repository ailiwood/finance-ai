"""Generate Ed25519 keypair for QuantSage license signing.

Run ONCE. Output:
  quantsage_private.key — keep safe, NEVER commit (add to .gitignore)
  Public key hex — hardcode into src/core/license.py

Usage: python scripts/gen_keypair.py
"""

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization

priv = Ed25519PrivateKey.generate()
pub = priv.public_key()

# Save private key (KEEP SAFE — this is your signing authority)
priv_bytes = priv.private_bytes(
    encoding=serialization.Encoding.Raw,
    format=serialization.PrivateFormat.Raw,
    encryption_algorithm=serialization.NoEncryption(),
)
with open("quantsage_private.key", "wb") as f:
    f.write(priv_bytes)

# Print public key for hardcoding into client
pub_bytes = pub.public_bytes(
    encoding=serialization.Encoding.Raw,
    format=serialization.PublicFormat.Raw,
)
pub_hex = pub_bytes.hex()

print("=" * 60)
print("Ed25519 Keypair Generated")
print("=" * 60)
print(f"\nPrivate key saved: quantsage_private.key ({len(priv_bytes)} bytes)")
print(f"\nPublic key (hex, hardcode into src/core/license.py):")
print(f"  {pub_hex}")
print(f"\nLength: {len(pub_hex)} chars")
print("\nNEXT STEPS:")
print("  1. Add quantsage_private.key to .gitignore")
print("  2. Back up quantsage_private.key (lose it = can't issue new licenses)")
print("  3. Hardcode the public key hex into src/core/license.py")
print("  4. Delete or secure this key — NEVER commit it")
print("=" * 60)
