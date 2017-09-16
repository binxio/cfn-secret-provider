include Makefile.mk

NAME=cfn-custom-secret-generator


deploy:
	aws s3 --region eu-west-1 cp target/$(NAME)-$(VERSION).zip s3://binxio-public-eu-west-1/lambdas/$(NAME)-$(VERSION).zip 
	aws s3api --region eu-west-1 put-object-acl --bucket binxio-public-eu-west-1 --acl public-read --key lambdas/$(NAME)-$(VERSION).zip 
	aws s3 --region eu-west-1 cp \
		s3://binxio-public-eu-west-1/lambdas/$(NAME)-$(VERSION).zip \
		s3://binxio-public-eu-west-1/lambdas/$(NAME)-latest.zip 

do-push: deploy


do-build: local-build

local-build: src/cfn_secret_generator.py venv requirements.txt
	mkdir -p target/content 
	pip install -t target/content -r requirements.txt
	cp -r src/* target/content
	find target/content -type d | xargs  chmod ugo+rx 
	find target/content -type f | xargs  chmod ugo+r 
	cd target/content && zip --quiet -9r ../../target/$(NAME)-$(VERSION).zip  *
	chmod ugo+r target/$(NAME)-$(VERSION).zip

venv: requirements.txt
	virtualenv venv  && \
	. ./venv/bin/activate && \
	pip install -r requirements.txt
	
clean:
	rm -rf venv target

test:
	. ./venv/bin/activate && \
		pip install nosetests && \
		cd src && \
		 nosetests ../tests/*.py

autopep:
	autopep8 --experimental --in-place --max-line-length 132 src/*.py tests/*.py

deploy-custom-resource:
	EXISTS=$$(aws cloudformation get-template-summary --stack-name $(NAME) 2>/dev/null) ; \
	if [[ -z $$EXISTS ]] ; then \
		aws cloudformation create-stack \
			--capabilities CAPABILITY_IAM \
			--stack-name $(NAME) \
			--template-body file://cloudformation/cfn-custom-resource-provider.json ; \
		aws cloudformation wait stack-create-complete  --stack-name $(NAME) ; \
	else \
		aws cloudformation update-stack \
			--capabilities CAPABILITY_IAM \
			--stack-name $(NAME) \
			--template-body file://cloudformation/cfn-custom-resource-provider.json ; \
		aws cloudformation wait stack-update-complete  --stack-name $(NAME) ; \
	fi

delete-custom-resource:
	aws cloudformation delete-stack --stack-name $(NAME)
	aws cloudformation wait stack-delete-complete  --stack-name $(NAME)

demo:
	aws cloudformation create-stack --stack-name $(NAME)-demo \
		--template-body file://cloudformation/demo-stack.json  
	aws cloudformation wait stack-create-complete  --stack-name $(NAME)-demo

delete-demo:
	aws cloudformation delete-stack --stack-name $(NAME)-demo 
	aws cloudformation wait stack-delete-complete  --stack-name $(NAME)-demo

