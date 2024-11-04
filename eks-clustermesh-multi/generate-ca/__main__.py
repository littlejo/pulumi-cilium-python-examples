import pulumi
from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import rsa
from datetime import datetime, timedelta
import base64

def generate_certificate_and_key(common_name: str, validity_days: int):
    key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend()
    )
    valid_from = datetime.utcnow()
    valid_until = valid_from + timedelta(days=validity_days)
    subject = x509.Name([
        x509.NameAttribute(x509.oid.NameOID.COMMON_NAME, common_name),
    ])
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(valid_from)
        .not_valid_after(valid_until)
        .add_extension(
            x509.BasicConstraints(ca=True, path_length=None),
            critical=True,
        )
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                content_commitment=False,
                key_encipherment=True,
                data_encipherment=False,
                key_agreement=False,
                crl_sign=False,
                encipher_only=False,
                decipher_only=False,
                key_cert_sign=True,
            ),
            critical=True,
        )
        .add_extension(
            x509.ExtendedKeyUsage(
                [x509.ExtendedKeyUsageOID.SERVER_AUTH, 
                 x509.ExtendedKeyUsageOID.CLIENT_AUTH]
            ),
            critical=False,
        )
        .add_extension(
            x509.SubjectKeyIdentifier.from_public_key(key.public_key()),
            critical=False,
        )
        .sign(key, hashes.SHA256(), default_backend())
    )

    ca_crt = base64.b64encode(cert.public_bytes(serialization.Encoding.PEM)).decode('utf-8')
    ca_key = base64.b64encode(key.private_bytes(encoding=serialization.Encoding.PEM,format=serialization.PrivateFormat.TraditionalOpenSSL,encryption_algorithm=serialization.NoEncryption())).decode('utf-8')
    return ca_crt, ca_key

ca_crt, ca_key = generate_certificate_and_key("Cilium CA", 1095)

pulumi.export("ca_crt", ca_crt)
pulumi.export("ca_key", ca_key)
