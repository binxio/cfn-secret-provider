# Custom::AccessKey
The `Custom::AccessKey` creates an Access Key, calculates the SMTP password and stores all credentials in the parameter store.

## Syntax
To declare this entity in your AWS CloudFormation template, use the following syntax:

```yaml
Resources:
    SMTPSecret:
      Type : Custom::AccessKey
      Properties:
        
Outputs:
    SMTPPassword:
        Value: !Ref SMTPSecret.Password
```

## Properties
You can specify the following properties:

- `SecretAccessKey`  - the secret access key to convert.

## Return values
With 'Fn::GetAtt' the following values are available:

- `Password` - the SMTP password based on the Secret access key.

For more information about using Fn::GetAtt, see [Fn::GetAtt](http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/intrinsic-function-reference-getatt.html).
