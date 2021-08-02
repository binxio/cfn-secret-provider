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
    SecretAccessKey:
        Value: !GetAtt AccessKey.SecretAccessKey
    SMTPPassword:
        Value: !GetAtt AccessKey.SMTPPassword
    Hash:
        Value: !GetAtt AccessKey.Hash
```

The access key id, access secret and the smtp password are stored in the parameter store under the paths `<ParameterPath>/aws_access_key_id`, `<ParameterPath>/aws_secret_access_key` and `<ParameterPath>/smtp_password` respectively.

## Properties
You can specify the following properties:

- `UserName`  - to create an access key for.
- `ParameterPath`  - into the parameter store to store the credentials.
- `Serial`  - to force the access key to be recycled.
- `Status`  - Active or Inactive.
- `ReturnSecret`  - returns access id and access secret as attribute.
- `ReturnPassword`  - returns access id and SMTP password as attribute.
- `NoEcho` - indicate whether output of the return values is replaced by `*****`, default True.
- `SMTPRegion` - to generate the SMTP password for, default region of the stack.

If you only update the `ParameterPath` the access key will be copied to the new path, and the parameters from the path 
will be removed.

## Return values
With 'Fn::GetAtt' the following values are available:

- `SMTPPassword` - the SMTP password based for the access key (if ReturnPassword is true).
- `SecretAccessKey` - the secret part of the access key (if ReturnSecret is true).
- `Hash` - a hash of the SMTP password to detect changes in the access key secret.

For more information about using Fn::GetAtt, see [Fn::GetAtt](http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/intrinsic-function-reference-getatt.html).
