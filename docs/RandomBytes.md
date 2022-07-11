# Custom::RandomBytes
The `Custom::RandomBytes` resource creates a parameter in the Parameter Store with SecureString value containing a randomized string.

An existing parameter in the Parameter Store will not be overwritten.

## Syntax
To declare this entity in your AWS CloudFormation template, use the following syntax:

```yaml
  Type : Custom::RandomBytes
  Properties : 
    Name : String
    Description : String
    Length : Integer
    KeyAlias : String
    ServiceToken : String
    RefreshOnUpdate: Boolean
    ReturnSecret: Boolean
    Version: String
```

## Properties
You can specify the following properties:

- `Name`  - the name of the parameter in the Parameter Store (required)
- `Description`  - for the parameter in the store. (Default '')
- `Length`  - the length of the secret in bytes (default `8`)
- `KeyAlias`  - to use to encrypt the string (default `alias/aws/ssm`)
- `ReturnSecret`  - as an attribute. (Default 'false')
- `RefreshOnUpdate`  - generate a new secret on update (Default 'false')
- `ServiceToken`  - ARN pointing to the lambda function implementing this resource
- `Version`  - optional, an opaque string to enforce the generation of a new secret.
- `NoEcho` - indicate whether output of the return values is replaced by `*****`, default True.

## Return values
With 'Fn::GetAtt' the following values are available:

- `Secret` - the generated secret value base64-encoded, if `ReturnSecret` was set to True.
- `Arn` - the AWS Resource name of the parameter.
- `Hash` - of the secret.
- `Version` - of the value in the store.
- `ParameterName` - name of the SSM parameter in which the secret is stored.

### Caveat - Version usage
Note that the input Version is just an opaque string to force an update of the key if RefreshOnUpdate is true, where
as the returned Version attribute is the actual version of the parameter value in the store.

For more information about using Fn::GetAtt, see [Fn::GetAtt](http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/intrinsic-function-reference-getatt.html).


