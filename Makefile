include Makefile.mk
USERNAME=xebia
NAME=cfn-secret-provider

AWS_REGION=eu-central-1
AWS_ACCOUNT=$(shell aws sts get-caller-identity --query Account --output text)
ALL_REGIONS=$(shell aws --region $(AWS_REGION) \
		ec2 describe-regions 		\
		--query 'join(`\n`, Regions[?RegionName != `$(AWS_REGION)`].RegionName)' \
		--output text)

REGISTRY_HOST=$(AWS_ACCOUNT).dkr.ecr.$(AWS_REGION).amazonaws.com
IMAGE=$(REGISTRY_HOST)/$(USERNAME)/$(NAME)
TAG_WITH_LATEST=never


Pipfile.lock: Pipfile requirements.txt test-requirements.txt

requirements.txt test-requirements.txt: Pipfile
	pipenv requirements > requirements.txt
	pipenv requirements --dev-only > test-requirements.txt

Pipfile.lock: Pipfile
	pipenv update

test: Pipfile.lock
	for n in ./cloudformation/*.yaml ; do aws cloudformation validate-template --template-body file://$$n ; done
	PYTHONPATH=$(PWD)/src pipenv run pytest ./tests/test*.py

pre-build: requirements.txt


fmt:
	black src/*.py tests/*.py

deploy-provider:  ## deploy the provider to the current account
	sed -i '' -e 's^$(NAME):[0-9]*\.[0-9]*\.[0-9]*[^\.]*^$(NAME):$(VERSION)^' cloudformation/cfn-resource-provider.yaml
	aws cloudformation deploy \
                --capabilities CAPABILITY_IAM \
                --stack-name $(NAME) \
                --template-file ./cloudformation/cfn-resource-provider.yaml

delete-provider:
	aws cloudformation delete-stack --stack-name $(NAME)
	aws cloudformation wait stack-delete-complete  --stack-name $(NAME)



deploy-pipeline: 
	aws cloudformation deploy \
                --capabilities CAPABILITY_IAM \
                --stack-name $(NAME)-pipeline \
                --template-file ./cloudformation/cicd-pipeline.yaml

delete-pipeline: 
	aws cloudformation delete-stack --stack-name $(NAME)-pipeline
	aws cloudformation wait stack-delete-complete  --stack-name $(NAME)-pipeline

demo:
	aws cloudformation deploy --stack-name $(NAME)-demo \
		--template-file ./cloudformation/demo-stack.yaml --capabilities CAPABILITY_NAMED_IAM \
                --parameter-overrides \
                        ApiKey=$(shell ./encrypt-secret CD98BD30-F944-4FD9-B86D-3F67664FBAEB);
	docker build -t $(NAME)-demo --build-arg STACK_NAME=$(NAME)-demo -f Dockerfile.demo .
	docker run -v  $(HOME)/.aws:/root/.aws \
		-e AWS_REGION=$(shell aws configure get region) \
		-e AWS_PROFILE=$${AWS_PROFILE:-default} \
		$(NAME)-demo

delete-demo:
	aws cloudformation delete-stack --stack-name $(NAME)-demo
	aws cloudformation wait stack-delete-complete  --stack-name $(NAME)-demo

