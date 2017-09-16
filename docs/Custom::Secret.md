# Custom::Secret
The `Custom::Secret` resource creates a parameter in the Parameter Store with SecureString value containing an randomized string.

An existing parameter in the Parameter Store will not be overwritten.

## Syntax
To declare this entity in your AWS CloudFormation template, use the following syntax:

```json
{
  "Type" : "Custom::Secret",
  "Properties" : {
    "Name" : String,
    "Alphabet" : String,
    "Length" : Integer,
    "KeyAlias" : String,
    "ServiceToken" : String
  }
}
```

## Properties
You can specify the following properties:

- `Name`  - the name of the parameter in the Parameter Store (required)
- `Alphabet` - the alphabet of characters from which to generate a secret (defaults to ASCII letters, digits and `!@#$^*+=`)
- `Length`  - the length of the secret (default `30`)
- `KeyAlias`  - to use to encrypt the string (default `alias/aws/ssm`)
- `ServiceToken`  - points the the lambda function deployed in your account

## Return values
With 'Fn::GetAtt' the following values are available:

- `Secret` - the generated secret value.
- `Arn` - the AWS Resource name of the parameter

For more information about using Fn::GetAtt, see [Fn::GetAtt](http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/intrinsic-function-reference-getatt.html).
