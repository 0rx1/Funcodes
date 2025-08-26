#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import argparse
from ssigie_helpers.AD_Helper import AD_Helper
import re
import sys
from datetime import datetime
from ssigie_utils.Mail_Utils import is_valid_email, send_email
import os
import pandas as pd
from openpyxl import load_workbook

def merge_excel_files(file_list, output_file, sheet_names):
    """
    Merge multiple Excel files into one file with multiple sheets
    
    Args:
        file_list: List of Excel file paths to merge
        output_file: Output file path for merged Excel
        sheet_names: List of sheet names for each file
    """
    try:
        # Create a new Excel writer
        with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
            for i, (file_path, sheet_name) in enumerate(zip(file_list, sheet_names)):
                if os.path.exists(file_path):
                    # Read the Excel file
                    df = pd.read_excel(file_path)
                    # Write to new sheet
                    df.to_excel(writer, sheet_name=sheet_name, index=False)
                    print(f"Merged {os.path.basename(file_path)} into sheet '{sheet_name}'")
                else:
                    print(f"Warning: File {file_path} not found, skipping...")
        
        print(f"Successfully created merged file: {output_file}")
        
    except Exception as e:
        print(f"Error merging Excel files: {str(e)}")
        raise

def main():
    parser=argparse.ArgumentParser(description="Utilitaire d'extraction des utilisateurs et groupes AD")
    parser.add_argument('--ad', choices=['GIECB', 'CB.LOCAL'], required=True, help="Spécifie l'AD à requêter: 'GIECB' ou 'CB.LOCAL'")
    parser.add_argument('--extract', choices=['users', 'members', 'groups', 'all'], required=True, help="Spécifie quoi exporter: 'users' pour les utilisateurs, 'groups' pour les groupes, 'members' pour les membres de groupes, 'all' pour tout exporter dans un seul fichier.")
    parser.add_argument('--mail', type=str, help='Adresse e-mail pour export (optionnel)')
    parser.add_argument('--output', type=str, help='Répertoire de sortie')
    parser.add_argument('--conf', type=str, help='Fichier de configuration')
    
    args=parser.parse_args()
    
    if args.mail:
        if not is_valid_email(args.mail):
            print(f"[{datetime.now().strftime('%d/%m/%Y %H:%M:%S')}][ERROR] {args.mail} is not a valid adress.")
            return 1
    
    dirtarget="./Outputs"
    if args.output:
        dirtarget=args.output
    if not os.path.exists(dirtarget):
        os.makedirs(dirtarget)
    
    conftarget="./config.ini"
    if args.conf:
        conftarget=args.conf
    
    # Chargement de AD_Helper - classe permettant de requêter l'AD selon les besoins
    ad_helper=AD_Helper(conftarget)
    
    if args.extract == 'users':
        # Extraction uniquement des utilisateurs
        output_file= f"{dirtarget}/Export_AD_Users_{args.ad}_{datetime.now().strftime('%Y-%m-%d')}.xlsx"
        ad_helper.get_users(args.ad, output_file)
        if args.mail:
            mail_subject=f"Export AD {args.ad} du {datetime.now().strftime('%d/%m/%Y')}"
            mail_body=f"Bonjour,\n\nCi-joint un export des utilisateurs de l'AD {args.ad}.\n\nCe message est automatique."
            
    elif args.extract == 'members':
        # Extraction des groupes et des utilisateurs
        output_file= f"{dirtarget}/Export_AD_GroupMembers_{args.ad}_{datetime.now().strftime('%Y-%m-%d')}.xlsx"
        ad_helper.get_user_groups(args.ad, output_file)
        if args.mail:
            mail_subject=f"Export des membres des groupes AD {args.ad} du {datetime.now().strftime('%d/%m/%Y')}"
            mail_body=f"Bonjour,\n\nCi-joint un export des groupes et de leurs membres de l'AD {args.ad}.\n\nCe message est automatique."
            
    elif args.extract == 'groups':
        # Extraction des groupes uniquement
        output_file=f"{dirtarget}/Export_AD_Groups_{args.ad}_{datetime.now().strftime('%Y-%m-%d')}.xlsx"
        ad_helper.get_groups(args.ad, output_file)
        if args.mail:
            mail_subject=f"Export des groupes AD {args.ad} du {datetime.now().strftime('%d/%m/%Y')}"
            mail_body=f"Bonjour,\n\nCi-joint un export des groupes de l'AD {args.ad}.\n\nCe message est automatique."
            
    elif args.extract == 'all':
        # Extraction complète: utilisateurs, groupes et membres dans des fichiers séparés puis fusion
        timestamp = datetime.now().strftime('%Y-%m-%d')
        
        # Extract users
        users_file = f"{dirtarget}/Export_AD_Users_{args.ad}_{timestamp}.xlsx"
        ad_helper.get_users(args.ad, users_file)
        
        # Extract groups
        groups_file = f"{dirtarget}/Export_AD_Groups_{args.ad}_{timestamp}.xlsx"
        ad_helper.get_groups(args.ad, groups_file)
        
        # Extract group members
        members_file = f"{dirtarget}/Export_AD_GroupMembers_{args.ad}_{timestamp}.xlsx"
        ad_helper.get_user_groups(args.ad, members_file)
        
        # Merge all files into one
        merged_file = f"{dirtarget}/Export_AD_Complete_{args.ad}_{timestamp}.xlsx"
        merge_excel_files([users_file, groups_file, members_file], merged_file, 
                         ['Users', 'Groups', 'GroupMembers'])
        
        # Clean up temporary files
        try:
            os.remove(users_file)
            os.remove(groups_file) 
            os.remove(members_file)
        except OSError as e:
            print(f"Warning: Could not remove temporary files: {e}")
        
        # Use merged file for output
        output_file = merged_file
        
        if args.mail:
            mail_subject=f"Export complet AD {args.ad} du {datetime.now().strftime('%d/%m/%Y')}"
            mail_body=f"Bonjour,\n\nCi-joint un export complet (utilisateurs, groupes et membres) de l'AD {args.ad} dans un seul fichier Excel avec plusieurs onglets.\n\nCe message est automatique."
            
    if args.mail:
        # Envoi du mail si demandé
        send_email(
            smtp_server='localhost',    # Local MTA (postfix configuré pour forward sur MTA fourni par SIG)
            sender_email='vmw@.com',
            receiver_email=args.mail,
            subject=mail_subject,
            body=mail_body,
            attachment_paths=[output_file]
        )

if __name__ == '__main__':
    main()
