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
    "KeySize": Integer,
    "KeyFormat": String,
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
- `KeySize` - Size of the RSA key, defaults to 2048.
- `KeyFormat` - 'PKCS8' or 'TraditionalOpenSSL', default 'PKCS8'
- `KeyAlias`  - to use to encrypt the key (default 'alias/aws/ssm')
- `Description`  - for the parameter in the store. (Default '')
- `ServiceToken`  - ARN pointing to the lambda function implementing this resource 
- `RefreshOnUpdate` - generate a new key on update, default false.
- `Version`  - an opaque string to enforce the generation of a new secret 

## Return values
With 'Fn::GetAtt' the following values are available:

- `PublicKey` - the public key of the generated key pair, OpenSSL format
- `PublicKeyPEM` - the public key of the generated key pair, in PEM format
- `Arn` - the AWS Resource name of the parameter
- `Hash` - of the public key
- `Version` - of the value in the store.

### Caveat - Version usage
Note that the input Version is just an opaque string to force an update of the key if RefreshOnUpdate is true, where as the returned Version attribute is the actual version of the parameter value in the store.


For more information about using Fn::GetAtt, see [Fn::GetAtt](http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/intrinsic-function-reference-getatt.html).
