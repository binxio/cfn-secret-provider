# Custom::RSAKey
The `Custom::RSAKey` resource creates a private RSA key in the Parameter Store.
An existing parameter in the Parameter Store will not be overwritten.

## Syntax
To declare this entity in your AWS CloudFormation template, use the following syntax:

```json
{
  "Type" : "Custom::RSAKey",
  "Properties" : {
    "Name" : String,
    "KeyAlias" : String,
    "ServiceToken" : String,
    "Description": String,
    "RefreshOnUpdate": Boolean,
    "Version": String
  }
}
```

## Properties
You can specify the following properties:

- `Name`  - the name of the key in the Parameter Store (required)
- `KeyAlias`  - to use to encrypt the key (default `alias/aws/ssm`)
- `Description`  - for the parameter in the store. (Default '')
- `ServiceToken`  - ARN pointing to the lambda function implementing this resource 
- `RefreshOnUpdate` - generate a new key on update, default false.
- `Version`  - an opaque string to enforce the generation of a new secret.

## Return values
With 'Fn::GetAtt' the following values are available:

- `PublicKey` - the public key of the generated key pair, OpenSSL format
- `PublicKeyPEM` - the public key of the generated key pair, in PEM format
- `Arn` - the AWS Resource name of the parameter
- `Hash` - of the public key

For more information about using Fn::GetAtt, see [Fn::GetAtt](http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/intrinsic-function-reference-getatt.html).
