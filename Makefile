include Makefile.mk

NAME=cfn-secret-provider
AWS_REGION=eu-central-1
ALL_REGIONS=$(shell printf "import boto3\nprint '\\\n'.join(map(lambda r: r['RegionName'], boto3.client('ec2').describe_regions()['Regions']))\n" | python | grep -v '^$(AWS_REGION)$$')

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
	@for REGION in $(ALL_REGIONS); do \
		echo "copying to region $$REGION.." ; \
		aws s3 --region $(AWS_REGION) \
			cp  \
			s3://binxio-public-$(AWS_REGION)/lambdas/$(NAME)-$(VERSION).zip \
			s3://binxio-public-$$REGION/lambdas/$(NAME)-$(VERSION).zip; \
		aws s3 --region $$REGION \
			cp  \
			s3://binxio-public-$$REGION/lambdas/$(NAME)-$(VERSION).zip \
			s3://binxio-public-$$REGION/lambdas/$(NAME)-latest.zip; \
		aws s3api --region $$REGION \
			put-object-acl --bucket binxio-public-$$REGION \
			--acl public-read --key lambdas/$(NAME)-$(VERSION).zip; \
		aws s3api --region $$REGION \
			put-object-acl --bucket binxio-public-$$REGION \
			--acl public-read --key lambdas/$(NAME)-latest.zip; \
	done
		

undeploy:
	@for REGION in $(ALL_REGIONS); do \
                echo "copying to region $$REGION.." ; \
                aws s3 --region $(AWS_REGION) \
                        rm  \
                        s3://binxio-public-$$REGION/lambdas/$(NAME)-$(VERSION).zip; \
        done


do-push: deploy

do-build: local-build

local-build: src/*.py venv requirements.txt
	mkdir -p target/content 
	docker run -v $$PWD/target/content:/venv python:2.7 pip install --quiet -t /venv $$(<requirements.txt)
	cp -r src/* target/content
	find target/content -type d | xargs  chmod ugo+rx 
	find target/content -type f | xargs  chmod ugo+r 
	cd target/content && zip --quiet -9r ../../target/$(NAME)-$(VERSION).zip  .
	chmod ugo+r target/$(NAME)-$(VERSION).zip

venv: requirements.txt
	virtualenv venv  && \
	. ./venv/bin/activate && \
	pip --quiet install --upgrade pip && \
	pip --quiet install -r requirements.txt 
	
clean:
	rm -rf venv target src/*.pyc tests/*.pyc

test: venv
	for n in ./cloudformation/*.yaml ; do aws cloudformation validate-template --template-body file://$$n ; done
	. ./venv/bin/activate && \
	pip --quiet install -r test-requirements.txt && \
	cd src && \
	PYTHONPATH=$(PWD)/src pytest ../tests/test*.py 

autopep:
	autopep8 --experimental --in-place --max-line-length 132 src/*.py tests/*.py

deploy-provider: 
	COMMAND=$(shell if aws cloudformation get-template-summary --stack-name $(NAME) >/dev/null 2>&1; then \
			echo update; else echo create; fi) ; \
	aws cloudformation $$COMMAND-stack \
		--capabilities CAPABILITY_IAM \
		--stack-name $(NAME) \
		--template-body file://cloudformation/cfn-resource-provider.yaml ; \
	aws cloudformation wait stack-$$COMMAND-complete  --stack-name $(NAME) 

delete-provider:
	aws cloudformation delete-stack --stack-name $(NAME)
	aws cloudformation wait stack-delete-complete  --stack-name $(NAME)

demo: 
	COMMAND=$(shell if aws cloudformation get-template-summary --stack-name $(NAME)-demo >/dev/null 2>&1; then \
			echo update; else echo create; fi) ; \
	aws cloudformation $$COMMAND-stack --stack-name $(NAME)-demo \
		--template-body file://cloudformation/demo-stack.yaml --capabilities CAPABILITY_NAMED_IAM;\
	aws cloudformation wait stack-$$COMMAND-complete  --stack-name $(NAME)-demo

delete-demo:
	aws cloudformation delete-stack --stack-name $(NAME)-demo 
	aws cloudformation wait stack-delete-complete  --stack-name $(NAME)-demo

