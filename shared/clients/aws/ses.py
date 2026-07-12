import boto3

from django.conf import settings


class SESProvider:

    def __init__(self):
        self.client = boto3.client(
            service_name="sesv2",
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_S3_REGION_NAME
        )

    def create_email_identity(self, domain):
        response = self.client.create_email_identity(
            EmailIdentity=domain
        )
        dkim_tokens = response["DkimAttributes"]["Tokens"]
        return {
            "verified": response["VerifiedForSendingStatus"],
            "dkim": [
                {
                    "type": "CNAME",
                    "host": f"{token}._domainkey.{domain}",
                    "value": f"{token}.dkim.amazonses.com"
                }
                for token in dkim_tokens
            ]
        }

    def get_email_identity(self, domain):
        response = self.client.get_email_identity(
            EmailIdentity=domain
        )
        return {
            "verified": response["VerifiedForSendingStatus"],
            "verification_status": response["VerificationStatus"],
            "dkim_status": response["DkimAttributes"]["Status"]
        }

    def send(
            self,
            sender,
            recipients,
            subject,
            html,
            reply_to=None
    ):
        response = self.client.send_email(
            FromEmailAddress=sender,
            Destination={
                "ToAddresses": recipients
            },
            ReplyToAddresses=[
                reply_to
            ] if reply_to else [],
            Content={
                "Simple": {
                    "Subject": {
                        "Data": subject
                    },
                    "Body": {
                        "Html": {
                            "Data": html
                        }
                    }
                }
            }
        )
        return {
            "message_id": response["MessageId"]
        }