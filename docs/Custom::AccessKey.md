# Custom::AccessKey
The `Custom::AccessKey` creates an Access Key, calculates the SMTP password and stores all credentials in the parameter store.

## Syntax
To declare this entity in your AWS CloudFormation template, use the following syntax:

```yaml
Resources:
  AccessKey:
    Type: Custom::AccessKey
    Properties:
      Description: sample user credential
      UserName: '<UserName>'
      ParameterPath: '<Parameter Path>'
      Serial: 1
      Status: Active
      ReturnSecret: false
      ReturnPassword: true
      NoEcho: false
      ServiceToken: !Sub 'arn:aws:lambda:${AWS::Region}:${AWS::AccountId}:function:binxio-cfn-secret-provider'
        
Outputs:
    AccessKeyId:
        Value: !Ref AccessKey
    AccessSecretKey:
        Value: !Ref AccessKey.AccessSecretKey
    SMTPPassword:
        Value: !Ref AccessKey.SMTPPassword
```

The access key id, access secret and the smtp password are stored in the parameter store under the paths `ParameterPath/aws_access_key_id`, `ParameterPath/aws_access_secret_key` and `ParameterPath/smtp_password` respectively. 

## Properties
You can specify the following properties:

- `UserName`  - to create an access key for.
- `ParameterPath`  - into the parameter store to store the credentials
- `Serial`  - to force the access key to be recycled
- `Status`  - Active or Inactive
- `ReturnSecret`  - returns access id and access secret as attribute
- `ReturnPassword`  - returns access id and SMTP password as attribute
- `NoEcho` - indicates whether the secret can be an output value, default 'True' meaning it cannot.   

## Return values
With 'Fn::GetAtt' the following values are available:

- `SMTPPassword` - the SMTP password based for the access key (if ReturnPassword is true).
- `AccessSecretKey` - the secret part of the access key (if ReturnSecret is true).

For more information about using Fn::GetAtt, see [Fn::GetAtt](http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/intrinsic-function-reference-getatt.html).
