include Makefile.mk

NAME=cfn-secret-provider
S3_BUCKET_PREFIX=binxio-public
AWS_REGION=eu-central-1
ALL_REGIONS=$(shell printf "import boto3\nprint('\\\n'.join(map(lambda r: r['RegionName'], boto3.client('ec2').describe_regions()['Regions'])))\n" | python | grep -v '^$(AWS_REGION)$$')

help:
	@echo 'make                 - builds a zip file to target/.'
	@echo 'make release         - builds a zip file and deploys it to s3.'
	@echo 'make clean           - the workspace.'
	@echo 'make test            - execute the tests, requires a working AWS connection.'
	@echo 'make deploy-provider - deploys the provider.'
	@echo 'make delete-provider - deletes the provider.'
	@echo 'make demo            - deploys the provider and the demo cloudformation stack.'
	@echo 'make delete-demo     - deletes the demo cloudformation stack.'

deploy: target/$(NAME)-$(VERSION).zip
	aws s3 --region $(AWS_REGION) \
		cp target/$(NAME)-$(VERSION).zip \
		s3://$(S3_BUCKET_PREFIX)-$(AWS_REGION)/lambdas/$(NAME)-$(VERSION).zip
	aws s3 --region $(AWS_REGION) cp \
		s3://$(S3_BUCKET_PREFIX)-$(AWS_REGION)/lambdas/$(NAME)-$(VERSION).zip \
		s3://$(S3_BUCKET_PREFIX)-$(AWS_REGION)/lambdas/$(NAME)-latest.zip
	aws s3api --region $(AWS_REGION) \
		put-object-acl --bucket $(S3_BUCKET_PREFIX)-$(AWS_REGION) \
		--acl public-read --key lambdas/$(NAME)-$(VERSION).zip
	aws s3api --region $(AWS_REGION) \
		put-object-acl --bucket $(S3_BUCKET_PREFIX)-$(AWS_REGION) \
		--acl public-read --key lambdas/$(NAME)-latest.zip

deploy-all-regions: deploy
	@for REGION in $(ALL_REGIONS); do \
		echo "copying to region $$REGION.." ; \
		aws s3 --region $(AWS_REGION) \
			cp  \
			s3://$(S3_BUCKET_PREFIX)-$(AWS_REGION)/lambdas/$(NAME)-$(VERSION).zip \
			s3://$(S3_BUCKET_PREFIX)-$$REGION/lambdas/$(NAME)-$(VERSION).zip; \
		aws s3 --region $$REGION \
			cp  \
			s3://$(S3_BUCKET_PREFIX)-$$REGION/lambdas/$(NAME)-$(VERSION).zip \
			s3://$(S3_BUCKET_PREFIX)-$$REGION/lambdas/$(NAME)-latest.zip; \
		aws s3api --region $$REGION \
			put-object-acl --bucket $(S3_BUCKET_PREFIX)-$$REGION \
			--acl public-read --key lambdas/$(NAME)-$(VERSION).zip; \
		aws s3api --region $$REGION \
			put-object-acl --bucket $(S3_BUCKET_PREFIX)-$$REGION \
			--acl public-read --key lambdas/$(NAME)-latest.zip; \
	done
		

undeploy:
	@for REGION in $(ALL_REGIONS); do \
                echo "removing lamdba from region $$REGION.." ; \
                aws s3 --region $(AWS_REGION) \
                        rm  \
                        s3://$(S3_BUCKET_PREFIX)-$$REGION/lambdas/$(NAME)-$(VERSION).zip; \
        done


do-push: deploy

do-build: target/$(NAME)-$(VERSION).zip

target/$(NAME)-$(VERSION).zip: src/*.py requirements.txt
	mkdir -p target/content
	docker build --build-arg ZIPFILE=$(NAME)-$(VERSION).zip -t $(NAME)-lambda:$(VERSION) -f Dockerfile.lambda . && \
		ID=$$(docker create $(NAME)-lambda:$(VERSION) /bin/true) && \
		docker export $$ID | (cd target && tar -xvf - $(NAME)-$(VERSION).zip) && \
		docker rm -f $$ID && \
		chmod ugo+r target/$(NAME)-$(VERSION).zip

venv: requirements.txt
	virtualenv -p python3 venv  && \
	. ./venv/bin/activate && \
	pip3 --quiet install --upgrade pip && \
	pip3 --quiet install -r requirements.txt
	
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

deploy-provider: COMMAND=$(shell if aws cloudformation get-template-summary --stack-name $(NAME) >/dev/null 2>&1; then \
			echo update; else echo create; fi)
deploy-provider:
	aws cloudformation $(COMMAND)-stack \
                --capabilities CAPABILITY_IAM \
                --stack-name $(NAME) \
                --template-body file://cloudformation/cfn-resource-provider.yaml \
                --parameters \
                        ParameterKey=S3BucketPrefix,ParameterValue=$(S3_BUCKET_PREFIX) \
                        ParameterKey=CFNCustomProviderZipFileName,ParameterValue=lambdas/$(NAME)-$(VERSION).zip
	aws cloudformation wait stack-$(COMMAND)-complete  --stack-name $(NAME)

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

