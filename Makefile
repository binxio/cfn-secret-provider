include Makefile.mk

NAME=cfn-secret-provider
AWS_REGION=eu-central-1

help:
	@echo 'make                 - builds a zip file to target/.'
	@echo 'make release         - builds a zip file and deploys it to s3.'
	@echo 'make clean           - the workspace.'
	@echo 'make test            - execute the tests, requires a working AWS connection.'
	@echo 'make deploy-provider - deploys the provider.'
	@echo 'make delete-provider - deletes the provider.'
	@echo 'make demo            - deploys the provider and the demo cloudformation stack.'
	@echo 'make delete-demo     - deletes the demo cloudformation stack.'

deploy:
	aws s3 --region $(AWS_REGION) \
		cp target/$(NAME)-$(VERSION).zip \
		s3://binxio-public-$(AWS_REGION)/lambdas/$(NAME)-$(VERSION).zip 
	aws s3 --region $(AWS_REGION) cp \
		s3://binxio-public-$(AWS_REGION)/lambdas/$(NAME)-$(VERSION).zip \
		s3://binxio-public-$(AWS_REGION)/lambdas/$(NAME)-latest.zip 
	aws s3api --region $(AWS_REGION) \
		put-object-acl --bucket binxio-public-$(AWS_REGION) \
		--acl public-read --key lambdas/$(NAME)-$(VERSION).zip 
	aws s3api --region $(AWS_REGION) \
		put-object-acl --bucket binxio-public-$(AWS_REGION) \
		--acl public-read --key lambdas/$(NAME)-latest.zip 

do-push: deploy

do-build: local-build

local-build: src/cfn_secret_provider.py venv requirements.txt
	mkdir -p target/content 
	pip --quiet install -t target/content -r requirements.txt
	cp -r src/* target/content
	find target/content -type d | xargs  chmod ugo+rx 
	find target/content -type f | xargs  chmod ugo+r 
	cd target/content && zip --quiet -9r ../../target/$(NAME)-$(VERSION).zip  *
	chmod ugo+r target/$(NAME)-$(VERSION).zip

venv: requirements.txt
	virtualenv venv  && \
	. ./venv/bin/activate && \
	pip --quiet install -r requirements.txt 
	
clean:
	rm -rf venv target

test: venv
	jq . cloudformation/*.json > /dev/null
	. ./venv/bin/activate && \
	pip --quiet install -r test-requirements.txt && \
	cd src && \
	nosetests ../tests/*.py 

autopep:
	autopep8 --experimental --in-place --max-line-length 132 src/*.py tests/*.py

deploy-provider:
	EXISTS=$$(aws cloudformation get-template-summary --stack-name $(NAME) 2>/dev/null) ; \
	if [[ -z $$EXISTS ]] ; then \
		aws cloudformation create-stack \
			--capabilities CAPABILITY_IAM \
			--stack-name $(NAME) \
			--template-body file://cloudformation/cfn-resource-provider.json ; \
		aws cloudformation wait stack-create-complete  --stack-name $(NAME) ; \
	else \
		aws cloudformation update-stack \
			--capabilities CAPABILITY_IAM \
			--stack-name $(NAME) \
			--template-body file://cloudformation/cfn-resource-provider.json ; \
		aws cloudformation wait stack-update-complete  --stack-name $(NAME) ; \
	fi

delete-provider:
	aws cloudformation delete-stack --stack-name $(NAME)
	aws cloudformation wait stack-delete-complete  --stack-name $(NAME)

demo: 
	aws cloudformation create-stack --stack-name $(NAME)-demo \
		--template-body file://cloudformation/demo-stack.json  
	aws cloudformation wait stack-create-complete  --stack-name $(NAME)-demo

delete-demo:
	aws cloudformation delete-stack --stack-name $(NAME)-demo 
	aws cloudformation wait stack-delete-complete  --stack-name $(NAME)-demo

