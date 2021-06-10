from flask import Flask, render_template, request, redirect, url_for, session
from boto3.dynamodb.conditions import Key, Attr

import requests
import boto3

app = Flask(__name__)
app.secret_key = 'af2ea574685f5a205b976c9e4adsd'

s3 = boto3.resource('s3')

### LOGIN PAGE ###
@app.route('/', methods=['GET', 'POST'])
def login(dynamodb=None):
	error_message = None

	if request.method == 'POST':
		currentUser_Email = request.form['email']
		currentUser_Password = request.form['password']

		if not dynamodb:
			dynamodb = boto3.resource('dynamodb', region_name='us-east-1')

		usersTable = dynamodb.Table('users')

		current_User = check_UserDetails(usersTable, currentUser_Email)

		if current_User['Items']:
			for user in current_User['Items']:
				userEmail = user['email']
				userPassword = user['password']

				if userPassword == currentUser_Password:
					session['current_User'] = userEmail

					if user['status'] == 'Not Verified':
						return redirect(url_for('kyc_verification'))
					else:	
						return redirect(url_for('dashboard'))
				else:
					error_message = "Invalid ID or password"
		else:
			error_message = "Invalid ID or password"			

	return render_template('index.html', error=error_message)

def check_UserDetails(usersTable, currentUser_Email):
	response = usersTable.query(KeyConditionExpression=Key('email').eq(currentUser_Email))
	return response

### REGISTRATION PAGE ###
@app.route('/registration', methods=['GET', 'POST'])
def registration(dynamodb=None):
	error_message = None

	if request.method == 'POST':
		newUser_code = request.form['code']
		newUser_name = request.form['name']
		newUser_address = request.form['address']
		newUser_contact = request.form['contact']
		newUser_siteURL = request.form['site_url']
		newUser_email = request.form['email']
		newUser_password = request.form['password']

		if not dynamodb:
			dynamodb = boto3.resource('dynamodb', region_name='us-east-1')

		usersTable = dynamodb.Table('users')

		existingUser = check_UserDetails(usersTable, newUser_email)

		if existingUser['Items']:
			error_message = "Account already exists! Please use your email to sign in."
			return redirect(url_for('login'))
		else:
			usersTable.put_item(
				Item={
						'merchant_code': newUser_code,
						'merchant': newUser_name,
						'merchant_address': newUser_address,
						'merchant_contact':newUser_contact,
						'site_url':newUser_siteURL,
						'email':newUser_email,
						'password':newUser_password,
						'status': 'Not Verified'
					}
				)
			return redirect(url_for('login'))

	return render_template('registration.html', error=error_message)

## ADD MERCHANT BANK ACCOUNT ##
@app.route('/add_MerchantBankAccount', methods=['GET', 'POST'])
def add_MerchantBankAccount(dynamodb=None):
	error_message = None

	if request.method == 'POST':
		accountName = request.form['account_name']
		accountBSB = request.form['account_bsb']
		accountNumber = request.form['account_number']
		account_LinkedPhoneNo = request.form['account_linkedNo']

		if not dynamodb:
			dynamodb = boto3.resource('dynamodb', region_name='us-east-1')

		accountsTable = dynamodb.Table('bank_accounts')

		existingBankAccount = checkAccountDetails(accountsTable, accountNumber)

		if existingBankAccount['Items']:
			error_message = "Bank Account already present. Add another account to continue."
		else:
			accountsTable.put_item(
				Item={
						'account_name': accountName,
						'account_bsb': accountBSB,
						'account_number': accountNumber,
						'account_LinkedPhoneNo':account_LinkedPhoneNo,
						'account_user': session['current_User'],
						'status': 'Inactive'
					}
				)
			return redirect(url_for('merchant_accounts'))
	return render_template('add_accounts.html', error=error_message)

def checkAccountDetails(accountsTable, accountNumber):
	response = accountsTable.scan(FilterExpression=Attr('account_number').eq(accountNumber))
	return response	


@app.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
	return render_template('home.html')

#Get list of merchant accounts
@app.route('/merchant_accounts', methods=['GET', 'POST'])
def merchant_accounts(dynamodb=None):
	error_message = None

	current_user = session['current_User']

	if not dynamodb:
		dynamodb = boto3.resource('dynamodb', region_name='us-east-1')

	accountsTable = dynamodb.Table('bank_accounts')

	merchantAccounts = fetch_MerchantAccounts(accountsTable, current_user)	

	return render_template('merchant_accounts.html', error=error_message, merchantAccounts=merchantAccounts)

def fetch_MerchantAccounts(accountsTable, current_user):
	response = accountsTable.query(KeyConditionExpression=Key('account_user').eq(current_user))	
	return response['Items']

#Merchant KYC verification
@app.route('/kyc_verification', methods=['GET', 'POST'])
def kyc_verification(dynamodb=None):
	error_message = None

	if request.method == 'POST':
		merchant_ABN = request.form['abn']
		document_proof = request.files['document']

		current_user = session['current_User']

		if not dynamodb:
			dynamodb = boto3.resource('dynamodb', region_name='us-east-1')

		usersTable = dynamodb.Table('users')

		merchant_Verified = check_MerchantVerified(usersTable, current_user)
		print(merchant_Verified)
		if merchant_Verified:
			print("if")
			return redirect(url_for('dashboard'))
		else:
			print("else")
			usersTable.update_item(
				Key={
					'email':current_user
				},
				UpdateExpression="set merchant_ABN=:a",
		        ExpressionAttributeValues={
		            ':a': merchant_ABN
		        },
		        ReturnValues="UPDATED_NEW"
			)

			upload_MerchantDocument(current_user, document_proof)
			return redirect(url_for('login'))			


	return render_template('kyc_verification.html', error=error_message)

def check_MerchantVerified(usersTable, current_user):
	response = usersTable.scan(FilterExpression=Attr('email').eq(current_user) & Attr('status').eq('Verified'))
	return response['Items']

def upload_MerchantDocument(current_user, document):
	document.filename = current_user + 'Documet'
	file_structure = current_user + '/' + document.filename
	s3.Bucket('s3820702-merchant-documents').put_object(Key=file_structure, Body=document)

@app.route('/transactions', methods=['GET', 'POST'])
def merchant_transactions(dynamodb=None):
	error_message = None
	current_user = session['current_User']

	if not dynamodb:
		dynamodb = boto3.resource('dynamodb', region_name='us-east-1')


	usersTable = dynamodb.Table('users')	
	transcationsTable = dynamodb.Table('transactions')

	merchant = check_UserDetails(usersTable, current_user)
	merchant_code = getMerchantCode(merchant)

	merchantTransactions = fetch_MerchantTransactions(transcationsTable, merchant_code)
	return render_template('transactions.html', error=error_message, merchantTransactions=merchantTransactions)

def getMerchantCode(merchant):
	for m in merchant['Items']:
		merchant_code = m['merchant_code']
	return merchant_code

def fetch_MerchantTransactions(transcationsTable, merchant_code):
	query_result = transcationsTable.scan(FilterExpression=Attr('merchant_code').eq(merchant_code))
	return query_result['Items']

### LOGOUT PAGE ###
@app.route('/logout', methods=['GET', 'POST'])
def logout():
	session.pop('username', None)
	return redirect(url_for('login'))

### APP RUN ###
if __name__ == '__main__':	
	app.run(host='127.0.0.1', port=8080, debug=True)