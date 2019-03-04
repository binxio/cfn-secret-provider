# Custom::KeyPair
The `Custom::KeyPair` resource creates a private keypair using the public key material.

## Syntax
To declare this entity in your AWS CloudFormation template, use the following syntax:

```json
{
  "Type" : "Custom::KeyPair",
  "Properties" : {
    "Name" : String,
    "PublicKeyMaterial" : String,
    "ServiceToken" : String
  }
}
```

## Properties
You can specify the following properties:

- `Name`  - the name of the keypair in ec2 (required).
- `PublicKeyMaterial` - the public key of the key pair (required).
- `ServiceToken`  - ARN pointing to the lambda function implementing this resource 

## Return values
With 'Fn::GetAtt' the following values are available:

- `Arn` - the AWS Resource Name of the keypair.
- `Name` - specified as the input key name pair.

For more information about using Fn::GetAtt, see [Fn::GetAtt](http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/intrinsic-function-reference-getatt.html).
