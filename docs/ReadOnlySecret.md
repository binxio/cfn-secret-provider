# Custom::ReadOnlySecret
The `Custom::ReadOnlySecret` reads a parameter value from the Parameter Store. The parameter must exist.


## Syntax
To declare this entity in your AWS CloudFormation template, use the following syntax:

```yaml
  Type : Custom:ReadOnlySecret
  Properties:
    Name: String
    Region: region-name
    ServiceToken: !Sub 'arn:aws:lambda:${AWS::Region}:${AWS::AccountId}:function:binxio-cfn-secret-provider'
```

## Properties
You can specify the following properties:

- `Name`  - the name of the parameter in the Parameter Store (required)
- `Region` - of the parameter store, default AWS::Region
- `ServiceToken`  - ARN pointing to the lambda function implementing this resource 

## Return values
With 'Fn::GetAtt' the following values are available:

- `Secret` - th retrieved value.
- `Arn` - the AWS Resource name of the parameter.
- `Hash` - of the secret.
- `Version` - of the value in the store.
- `ParameterName` - name of the SSM parameter in which the secret is stored.
