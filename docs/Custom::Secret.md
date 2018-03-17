# Custom::Secret
The `Custom::Secret` resource creates a parameter in the Parameter Store with SecureString value containing an randomized string. You can also explicit set a value.

An existing parameter in the Parameter Store will not be overwritten.

## Syntax
To declare this entity in your AWS CloudFormation template, use the following syntax:

```json
{
  "Type" : "Custom::Secret",
  "Properties" : {
    "Name" : String,
    "Description" : String,
    "Alphabet" : String,
    "Length" : Integer,
    "KeyAlias" : String,
    "Content" : String,
    "ServiceToken" : String,
    "RefreshOnUpdate": Boolean,
    "ReturnSecret": Boolean,
    "Version": String
  }
}
```

## Properties
You can specify the following properties:

- `Name`  - the name of the parameter in the Parameter Store (required)
- `Description`  - for the parameter in the store. (Default '')
- `Alphabet` - the alphabet of characters from which to generate a secret (defaults to ASCII letters, digits and punctuation characters)
- `Length`  - the length of the secret (default `30`)
- `KeyAlias`  - to use to encrypt the string (default `alias/aws/ssm`)
- `ReturnSecret`  - as an attribute. (Default 'false')
- `RefreshOnUpdate`  - generate a new secret on update (Default 'false')
- `ServiceToken`  - ARN pointing to the lambda function implementing this resource 
- `Version`  - optional, an opaque string to enforce the generation of a new secret.
- `NoEcho` - indicate whether output of the return values is replaced by `*****`, default True.

If you need to set a particular value to a SecureString parameter, you can specify:

- `Content`  - the value of the parameter in the Parameter Store. If given, **no** randomized string will be generated (default `empty`)

## Return values
With 'Fn::GetAtt' the following values are available:

- `Secret` - the generated secret value, if `ReturnSecret` was set to True.
- `Arn` - the AWS Resource name of the parameter.
- `Hash` - of the secret.
- `Version` - of the value in the store.

### Caveat - Version usage
Note that the input Version is just an opaque string to force an update of the key if RefreshOnUpdate is true, where as the returned Version attribute is the actual version of the parameter value in the store.

For more information about using Fn::GetAtt, see [Fn::GetAtt](http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/intrinsic-function-reference-getatt.html).
