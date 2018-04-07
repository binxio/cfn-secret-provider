# Custom::SecretsManagerSecret
The `Custom::SecretsManagerSecret` resource creates a secret in the new [AWS Secret Manager](https://docs.aws.amazon.com/secretsmanager).


## Syntax
To declare this resource in your AWS CloudFormation template, use the following syntax:

```json
{
  "Type" : "Custom::SecretsManagerSecret",
  "Properties" : {
    "Name" : String,
    "Description" : String,
    "KmsKeyId" : String,
    "SecretBinary" : String,
    "SecretString" : String, Array or Object,
    "RecoveryWindowInDays": Integer,
    "ClientRequestToken": String,
    "ServiceToken" : String,
    "NoEcho" : Boolean,
    "Tags": [ { "Key", String, "Value": String}, ...]
  }
}
```

## Properties
You can specify the following properties:

- `Name`  - the name of the secret in the Secrets Manager (required)
- `Description`  - for the secret. (Default '')
- `KmsKeyId`  - to use to encrypt the secret (Default 'alias/aws/secretsmanager')
- `SecretBinary` - Base64 encoded binary secret.
- `SecretString` - secret string or object to store as secret.
- `Tags` - array of tags for the secret.
- `RecoveryWindowInDays` - number of days a deleted secret can be restored (>= 7 and <= 30).
- `NoEcho` - indicate whether output of the return values is replaced by `*****`, default True.
- `ClientRequestToken` - a unique identifier for the new version to ensure idempotency.
- `ServiceToken`  - ARN pointing to the lambda function implementing this resource 

On successful completion, the ARN of the secret is returned.

## Return values
With 'Fn::GetAtt' the following values are available:

- `VersionId` - of the secret.

For more information about using Fn::GetAtt, see [Fn::GetAtt](http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/intrinsic-function-reference-getatt.html).
