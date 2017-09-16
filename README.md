# cfn-custom-secret-provider
A CloudFormation custom resource provider for managing secrets

One of the biggest problems I encounter in creating immutable infrastructures, is dealing with secrets. Secrets must always be different per
environment and therefore parameterized. As we automated all the things passwords often end up in parameter files and have to pass them around 
to people and applications: This is not a good thing. With this Custom CloudFormation Resource we put an end to that. Secrets are generated, 
stored in the EC2 parameter store and access to the secrets can be controlled through security policies.

## How does it work?
It is quite easy: you specify a CloudFormation resource of the [Custom::Secret](docs/Custom%3A%3ASecret.md), as follows:

```json
  "Resources": {
    "DBPassword": {
      "Type": "Custom::Secret",
      "Properties": {
        "Name": "/postgres/root/PGPASSWORD",
        "KeyAlias": "alias/aws/ssm",
        "Alphabet": "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_@#!",
        "Length": 30,
        "ServiceToken": { "Fn::Join": [ ":", [ "arn:aws:lambda", { "Ref": "AWS::Region" }, { "Ref": "AWS::AccountId" }, "function:CFNCustomSecretProvider" ] ]
        }
      }
    }
  }
```
After the deployment, a 30 character random string can be found in the EC Parameter Store with the name `/test-api/postgres/root/PGPASSWORD`.

If you need to access the secret in your cloudformation module, you can do that too.

```json
        "MasterUserPassword": { "Fn::GetAtt": [ "DBPassword", "Secret" ]}
```

## Installation
To install this Custom Resource, type:

```sh
aws cloudformation create-stack \
	--capabilities CAPABILITY_IAM \
	--stack-name cfn-custom-secret-provider \
	--template-body file://cloudformation/cfn-custom-resource-provider.json 

aws cloudformation wait stack-create-complete  --stack-name cfn-custom-secret-provider 
```

This CloudFormation template will use our pre-packaged provider from `s3://binxio-public/lambdas/cfn-custom-secret-provider-latest.zip`.


## Demo
To install the simple sample of the Custom Resource, type:

```sh
aws cloudformation create-stack --stack-name cfn-custom-secret-provider-demo \
	--template-body file://cloudformation/demo-stack.json
aws cloudformation wait stack-create-complete  --stack-name cfn-custom-secret-provider-demo
```

to validate the result, type:

```sh
aws ssm get-parameter --name /prod/postgres/root/PGPASSWORD 
```

## Conclusion
With this solution: 

- secrets are generated per environment
- always stored encrypted in the parameter store 
- where access to the secrets is audited and controlled!

