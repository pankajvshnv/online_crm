-- MySQL dump 10.13  Distrib 26.10.0, for macos15 (arm64)
--
-- Host: 127.0.0.1    Database: online_crm
-- ------------------------------------------------------
-- Server version	26.10.0

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!50503 SET NAMES utf8mb4 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

--
-- Table structure for table `calling_apis`
--

DROP TABLE IF EXISTS `calling_apis`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `calling_apis` (
  `id` int NOT NULL AUTO_INCREMENT,
  `calling_api_uuid` varchar(40) COLLATE utf8mb4_general_ci NOT NULL,
  `api_name` varchar(150) COLLATE utf8mb4_general_ci NOT NULL,
  `api_link` text COLLATE utf8mb4_general_ci NOT NULL,
  `server_host` varchar(150) COLLATE utf8mb4_general_ci NOT NULL,
  `server_username` varchar(150) COLLATE utf8mb4_general_ci NOT NULL,
  `server_password` varchar(255) COLLATE utf8mb4_general_ci NOT NULL,
  `server_db_name` varchar(150) COLLATE utf8mb4_general_ci NOT NULL,
  `source_variable` varchar(100) COLLATE utf8mb4_general_ci NOT NULL,
  `destination_variable` varchar(100) COLLATE utf8mb4_general_ci NOT NULL,
  `status` tinyint(1) NOT NULL DEFAULT '1',
  `created_by` varchar(40) COLLATE utf8mb4_general_ci NOT NULL,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT NULL ON UPDATE CURRENT_TIMESTAMP,
  `provider_type` varchar(50) COLLATE utf8mb4_general_ci NOT NULL DEFAULT 'issabel',
  `token_id` varchar(255) COLLATE utf8mb4_general_ci DEFAULT NULL,
  `default_did` varchar(50) COLLATE utf8mb4_general_ci DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_calling_api_uuid` (`calling_api_uuid`)
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `calling_apis`
--

LOCK TABLES `calling_apis` WRITE;
/*!40000 ALTER TABLE `calling_apis` DISABLE KEYS */;
INSERT INTO `calling_apis` VALUES (1,'a866ee29-6182-4027-a73c-6846f1c9e832','Cloud PBX Issabel','http://127.0.0.1:8088/ari','pbx.apexwealth.internal','asterisk_user','secretpass123','asteriskcdrdb','src_ext','dst_num',1,'admin','2026-11-21 12:28:51',NULL,'issabel',NULL,'+918049000100');
/*!40000 ALTER TABLE `calling_apis` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `chat_messages`
--

DROP TABLE IF EXISTS `chat_messages`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `chat_messages` (
  `id` int NOT NULL AUTO_INCREMENT,
  `chat_uuid` varchar(64) COLLATE utf8mb4_general_ci NOT NULL,
  `sender_user_id` int NOT NULL,
  `receiver_user_id` int DEFAULT NULL,
  `message_text` longtext COLLATE utf8mb4_general_ci NOT NULL,
  `attachment_path` varchar(255) COLLATE utf8mb4_general_ci DEFAULT NULL,
  `is_read` tinyint(1) DEFAULT '0',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_sender_receiver` (`sender_user_id`,`receiver_user_id`),
  KEY `idx_created_at` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `chat_messages`
--

LOCK TABLES `chat_messages` WRITE;
/*!40000 ALTER TABLE `chat_messages` DISABLE KEYS */;
/*!40000 ALTER TABLE `chat_messages` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `clients`
--

DROP TABLE IF EXISTS `clients`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `clients` (
  `id` int NOT NULL AUTO_INCREMENT,
  `client_uuid` varchar(40) COLLATE utf8mb4_general_ci NOT NULL,
  `lead_id` int NOT NULL,
  `sales_order_id` int DEFAULT NULL,
  `sales_order_uuid` varchar(40) COLLATE utf8mb4_general_ci DEFAULT NULL,
  `created_by_user_id` int NOT NULL,
  `client_code` varchar(60) COLLATE utf8mb4_general_ci NOT NULL,
  `client_name` varchar(160) COLLATE utf8mb4_general_ci DEFAULT NULL,
  `mobile_number` varchar(255) COLLATE utf8mb4_general_ci DEFAULT NULL,
  `email` varchar(160) COLLATE utf8mb4_general_ci DEFAULT NULL,
  `product_name` varchar(255) COLLATE utf8mb4_general_ci DEFAULT NULL,
  `plan_name` varchar(255) COLLATE utf8mb4_general_ci DEFAULT NULL,
  `service_start_date` date DEFAULT NULL,
  `service_expiry_date` date DEFAULT NULL,
  `total_amount` decimal(12,2) DEFAULT '0.00',
  `tax_amount` decimal(12,2) DEFAULT '0.00',
  `grand_total` decimal(12,2) DEFAULT '0.00',
  `so_status` varchar(50) COLLATE utf8mb4_general_ci DEFAULT 'approved',
  `address` text COLLATE utf8mb4_general_ci,
  `state` varchar(100) COLLATE utf8mb4_general_ci DEFAULT NULL,
  `city` varchar(100) COLLATE utf8mb4_general_ci DEFAULT NULL,
  `client_status` varchar(40) COLLATE utf8mb4_general_ci NOT NULL DEFAULT 'active',
  `notes` text COLLATE utf8mb4_general_ci,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `created_by_name` varchar(255) COLLATE utf8mb4_general_ci DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_clients_uuid` (`client_uuid`),
  UNIQUE KEY `uq_clients_sales_order_uuid` (`sales_order_uuid`),
  KEY `idx_clients_user_id` (`created_by_user_id`),
  KEY `idx_clients_status` (`client_status`),
  KEY `idx_clients_lead_id` (`lead_id`),
  KEY `idx_clients_code` (`client_code`),
  CONSTRAINT `fk_clients_lead` FOREIGN KEY (`lead_id`) REFERENCES `leads` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_clients_user` FOREIGN KEY (`created_by_user_id`) REFERENCES `users` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=14 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `clients`
--

LOCK TABLES `clients` WRITE;
/*!40000 ALTER TABLE `clients` DISABLE KEYS */;
INSERT INTO `clients` VALUES (1,'0af05b21-76e8-407b-a312-e90ac516406c',1,7,'eb825cbe-0f4a-44fd-a4c8-64e5c6012376',1,'CL-1001','Rajesh Mehta','9811001101','rajesh.mehta@example.com','Equity Premium Advisory','yearly','2026-11-21','2027-05-20',120000.00,21600.00,141600.00,'approved','Suite 402, Trade Tower, Bandra Kurla Complex','Maharashtra','Mumbai','active','High net-worth account. SEBI KYC verified.','2026-11-21 00:00:00','2026-11-21 13:00:04','System Administrator'),(2,'1f993a8f-6949-4208-9aff-533fe742ff39',2,8,'0a136ed4-e55f-4a51-abdb-faa9da32c361',2,'CL-1002','Anita Desai','9811001102','anita.desai@example.com','Options & Derivatives Strategy','quarterly','2026-11-18','2027-02-16',48000.00,8640.00,56640.00,'approved','7th Floor, Koregaon Park Plaza','Maharashtra','Pune','active','Active index options trader. Risk profiling score: 85/100.','2026-11-18 00:00:00','2026-11-21 13:00:04','System Administrator'),(3,'bd40cb9f-1de1-4ead-bf08-f1f641250a19',3,9,'55c818ea-5e59-4279-ba5f-c20ab667bc10',3,'CL-1003','Vikram Joshi','9811001103','vikram.j@example.com','Commodity Bullion Pack','monthly','2026-11-15','2026-12-15',18000.00,3240.00,21240.00,'approved','12/A 100ft Road, Indiranagar','Karnataka','Bangalore','active','Focus on MCX Gold & Silver delivery signals.','2026-11-15 00:00:00','2026-11-21 13:00:04','System Administrator'),(4,'b4446406-bbf9-452a-b284-3f6f51a9cf09',4,10,'fe6549c9-aec6-4255-b377-58ab4c7314ac',4,'CL-1004','Sunita Rao','9811001104','sunita.rao@example.com','Future Growth Advisory','six_monthly','2026-11-12','2027-05-11',75000.00,13500.00,88500.00,'approved','Plot 88, Financial District, Gachibowli','Telangana','Hyderabad','active','Corporate advisory account. Mandate signed.','2026-11-12 00:00:00','2026-11-21 13:00:04','System Administrator'),(5,'afe1d49d-efe8-4170-aae6-795f9000b25b',5,11,'21d9593a-df6d-4d49-999f-8fe74d10d843',1,'CL-1005','Rohan Malhotra','9811001105','rohan.m@example.com','HNI Wealth Portfolio','yearly','2026-11-09','2027-11-09',380000.00,68400.00,448400.00,'approved','B-14 Barakhamba Road, Connaught Place','Delhi','Delhi','active','Multi-asset portfolio advisory with quarterly rebalancing.','2026-11-09 00:00:00','2026-11-21 13:00:04','System Administrator'),(6,'33cf12c2-d19a-430b-aa5b-022ad81f443d',6,12,'23a76398-14d0-4095-9678-9acfae4ecfeb',2,'CL-1006','Manish Kulkarni','9811001106','manish.k@example.com','Options & Derivatives Strategy','monthly','2026-11-06','2026-12-06',20000.00,3600.00,23600.00,'approved','Block C, Titanium City Centre, Satellite','Gujarat','Ahmedabad','active','Intraday BankNifty strategy subscriber.','2026-11-06 00:00:00','2026-11-21 13:00:04','System Administrator'),(7,'450a8ae9-95a0-4c1c-bb1f-d51c299c7d1a',7,13,'019f561a-8295-458f-b531-70fe5c83e2d0',3,'CL-1007','Pooja Singhania','9811001107','pooja.s@example.com','HNI Wealth Portfolio','quarterly','2026-11-03','2027-02-01',115000.00,20700.00,135700.00,'approved','Park Street Chambers, 3rd Floor','West Bengal','Kolkata','active','Family office portfolio allocation client.','2026-11-03 00:00:00','2026-11-21 13:00:04','System Administrator'),(8,'27caaf18-dfee-4d3a-ba8d-b4f6de14312e',8,14,'b4f61307-830b-46f3-b68b-81eb9789d864',4,'CL-1008','Kavita Nair','9811001108','kavita.nair@example.com','Equity Premium Advisory','monthly','2026-10-31','2026-11-30',15000.00,2700.00,17700.00,'approved','Marine Drive Towers, Ernakulam','Kerala','Kochi','active','Swing trading recommendations with SMS alerts.','2026-10-31 00:00:00','2026-11-21 13:00:04','System Administrator'),(9,'4e25ea16-1699-494f-832c-e80af9c6b734',9,15,'c684e275-f3dc-4d36-b909-b33e8d21a14c',1,'CL-1009','Arjun Reddy','9811001109','arjun.reddy@example.com','Commodity Bullion Pack','quarterly','2026-10-28','2027-01-26',42000.00,7560.00,49560.00,'approved','Anna Salai Business Hub, Mount Road','Tamil Nadu','Chennai','active','Base metals & energy advisory pack.','2026-10-28 00:00:00','2026-11-21 13:00:04','System Administrator'),(10,'82dcea34-0cf2-4ab5-99b1-11158d9e3488',10,16,'ac499869-8c9e-4546-aec0-389b6b5db095',2,'CL-1010','Deepak Bansal','9811001110','deepak.b@example.com','Equity Premium Advisory','quarterly','2026-10-25','2027-01-23',38000.00,6840.00,44840.00,'approved','MI Road Commerce Complex','Rajasthan','Jaipur','active','Equity delivery and positional swing calls.','2026-10-25 00:00:00','2026-11-21 13:00:04','System Administrator'),(11,'970572fd-d71a-4736-863a-43e4705c15d9',13,17,'55e24cd8-d17d-405f-b032-fac92ff660a0',1,'CL-1011','Aditya Singhal','9811001113','aditya.singhal@example.com','HNI Wealth Portfolio','yearly','2026-10-22','2027-10-22',380000.00,68400.00,448400.00,'approved','Sector 62 Institutional Area','Uttar Pradesh','Noida','active','Treasury funds advisory with monthly performance audit.','2026-10-22 00:00:00','2026-11-21 13:00:04','System Administrator'),(12,'0cfaf62b-40c7-4612-ae10-4145bed6c1f3',14,18,'f600492c-8a84-43eb-aace-74e27e6969a8',2,'CL-1012','Bhavna Shah','9811001114','bhavna.shah@example.com','Future Growth Advisory','quarterly','2026-10-19','2027-01-17',39000.00,7020.00,46020.00,'approved','Ring Road Diamond Market','Gujarat','Surat','active','Midcap wealth compounder portfolio.','2026-10-19 00:00:00','2026-11-21 13:00:04','System Administrator'),(13,'651524d3-c388-47df-81dc-c9e84e8b2f62',17,19,'75b86953-2b3b-4b1f-8f6d-5b56cb7b69bb',5,'CL-1013','Naveen Chawla','9811001117','naveen.c@example.com','Options & Derivatives Strategy','quarterly','2026-10-16','2027-01-14',48000.00,8640.00,56640.00,'approved','AB Road Tech Park','Madhya Pradesh','Indore','active','Automated hedging recommendations.','2026-10-16 00:00:00','2026-11-21 13:00:04','System Administrator');
/*!40000 ALTER TABLE `clients` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `contacts`
--

DROP TABLE IF EXISTS `contacts`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `contacts` (
  `id` int NOT NULL AUTO_INCREMENT,
  `contact_uuid` varchar(40) COLLATE utf8mb4_general_ci NOT NULL,
  `lead_id` int NOT NULL,
  `created_by_user_id` int NOT NULL,
  `contact_name` varchar(160) COLLATE utf8mb4_general_ci DEFAULT NULL,
  `mobile_number` varchar(255) COLLATE utf8mb4_general_ci DEFAULT NULL,
  `email` varchar(160) COLLATE utf8mb4_general_ci DEFAULT NULL,
  `address` varchar(255) COLLATE utf8mb4_general_ci DEFAULT NULL,
  `product_id` int DEFAULT NULL,
  `plan_type` varchar(100) COLLATE utf8mb4_general_ci DEFAULT NULL,
  `notes` text COLLATE utf8mb4_general_ci,
  `status` tinyint(1) NOT NULL DEFAULT '1',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `created_by_name` varchar(255) COLLATE utf8mb4_general_ci DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_contacts_uuid` (`contact_uuid`),
  KEY `idx_contacts_lead_id` (`lead_id`),
  KEY `idx_contacts_user_id` (`created_by_user_id`),
  CONSTRAINT `fk_contacts_lead` FOREIGN KEY (`lead_id`) REFERENCES `leads` (`id`),
  CONSTRAINT `fk_contacts_user` FOREIGN KEY (`created_by_user_id`) REFERENCES `users` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=14 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `contacts`
--

LOCK TABLES `contacts` WRITE;
/*!40000 ALTER TABLE `contacts` DISABLE KEYS */;
INSERT INTO `contacts` VALUES (1,'24221e3e-4521-43e4-a988-b1f4f53e987f',1,1,'Rajesh Mehta','9811001101','rajesh.mehta@example.com','Bandra Kurla Complex, Mumbai, MH',5,'yearly','Managing Director, Mehta Global Ventures. Prefers communication via executive assistant.',1,'2026-11-21 13:00:04','2026-11-21 13:00:04','System Administrator'),(2,'b2b9e1c2-8f86-452b-99b6-771a8d8c2646',2,2,'Anita Desai','9811001102','anita.desai@example.com','Koregaon Park Plaza, Pune, MH',2,'quarterly','Proprietary trader focusing on Bank Nifty index weekly option spreads.',1,'2026-11-20 13:00:04','2026-11-21 13:00:04','System Administrator'),(3,'e4190590-d2a4-4ac1-82c1-49542b3e267e',3,3,'Vikram Joshi','9811001103','vikram.j@example.com','100ft Road, Indiranagar, Bangalore, KA',3,'monthly','Chief Technology Officer at FinCorp. Trades MCX Gold and Silver bullion delivery.',1,'2026-11-19 13:00:04','2026-11-21 13:00:04','System Administrator'),(4,'3f7d8342-ab9f-4311-b5d2-ef2f4986df49',4,4,'Sunita Rao','9811001104','sunita.rao@example.com','Gachibowli Financial Hub, Hyderabad, TS',6,'six_monthly','Family Office Trustee. Requires monthly portfolio NAV and allocation summaries.',1,'2026-11-18 13:00:04','2026-11-21 13:00:04','System Administrator'),(5,'dc15f1bb-dbeb-4281-96e8-b5fb7dae22ef',5,1,'Rohan Malhotra','9811001105','rohan.m@example.com','Connaught Place, Central Delhi, DL',6,'yearly','Corporate treasury head. Focuses on capital preservation with alpha overlays.',1,'2026-11-17 13:00:04','2026-11-21 13:00:04','System Administrator'),(6,'0b3562e6-d8c3-4270-bade-7c0f382d7921',6,2,'Manish Kulkarni','9811001106','manish.k@example.com','Titanium City Centre, Ahmedabad, GJ',2,'monthly','Active day trader. Uses automated API signals for option executions.',1,'2026-11-16 13:00:04','2026-11-21 13:00:04','System Administrator'),(7,'4956d1df-093e-44ed-b8e8-b1749174fd4a',7,3,'Pooja Singhania','9811001107','pooja.s@example.com','Park Street, Central Kolkata, WB',6,'quarterly','Principal at Singhania Capital. Dedicated Relationship Manager assigned.',1,'2026-11-15 13:00:04','2026-11-21 13:00:04','System Administrator'),(8,'98207b5c-6ff6-42a8-b7f6-be8e646e00a4',8,4,'Kavita Nair','9811001108','kavita.nair@example.com','Marine Drive Towers, Kochi, KL',5,'monthly','Long-term investor shifting active capital into momentum swing ideas.',1,'2026-11-14 13:00:04','2026-11-21 13:00:04','System Administrator'),(9,'97fb42e1-7ffc-4a9c-8311-f29239183a7e',9,1,'Arjun Reddy','9811001109','arjun.reddy@example.com','Mount Road Business Center, Chennai, TN',3,'quarterly','Commodity exporter managing price hedging on copper and crude oil.',1,'2026-11-13 13:00:04','2026-11-21 13:00:04','System Administrator'),(10,'71f25a77-2950-41e6-84b2-2768588a5841',10,2,'Deepak Bansal','9811001110','deepak.b@example.com','MI Road Commerce Hub, Jaipur, RJ',5,'quarterly','Retail franchise owner looking for short-term swing advisory.',1,'2026-11-12 13:00:04','2026-11-21 13:00:04','System Administrator'),(11,'af082724-8834-46ac-9268-7b5d64d5de38',13,1,'Aditya Singhal','9811001113','aditya.singhal@example.com','Sector 62 IT Park, Noida, UP',6,'yearly','Angel investor with diverse equity and startup advisory holdings.',1,'2026-11-11 13:00:04','2026-11-21 13:00:04','System Administrator'),(12,'9f0919a1-9d9d-4e8e-8d19-326ecebdcba4',14,2,'Bhavna Shah','9811001114','bhavna.shah@example.com','Ring Road Diamond Market, Surat, GJ',7,'quarterly','Diamond merchant seeking wealth diversification in small and mid-cap stocks.',1,'2026-11-10 13:00:04','2026-11-21 13:00:04','System Administrator'),(13,'5e130302-8ee9-47e4-afb9-6e5c3eb108a8',17,5,'Naveen Chawla','9811001117','naveen.c@example.com','AB Road Tech Hub, Indore, MP',2,'quarterly','Software engineering director with deep interest in quantitative options strategies.',1,'2026-11-09 13:00:04','2026-11-21 13:00:04','System Administrator');
/*!40000 ALTER TABLE `contacts` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `crm_cdr`
--

DROP TABLE IF EXISTS `crm_cdr`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `crm_cdr` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `provider` varchar(50) COLLATE utf8mb4_general_ci NOT NULL DEFAULT 'issabel',
  `uniqueid` varchar(100) COLLATE utf8mb4_general_ci NOT NULL,
  `calldate` datetime NOT NULL,
  `src` varchar(80) COLLATE utf8mb4_general_ci NOT NULL DEFAULT '',
  `dst` varchar(80) COLLATE utf8mb4_general_ci NOT NULL DEFAULT '',
  `clid` varchar(150) COLLATE utf8mb4_general_ci DEFAULT '',
  `channel` varchar(100) COLLATE utf8mb4_general_ci DEFAULT '',
  `dstchannel` varchar(100) COLLATE utf8mb4_general_ci DEFAULT '',
  `dcontext` varchar(80) COLLATE utf8mb4_general_ci DEFAULT '',
  `duration` int DEFAULT '0',
  `billsec` int DEFAULT '0',
  `disposition` varchar(45) COLLATE utf8mb4_general_ci NOT NULL DEFAULT 'NO ANSWER',
  `recordingfile` varchar(500) COLLATE utf8mb4_general_ci DEFAULT '',
  `call_direction` varchar(20) COLLATE utf8mb4_general_ci DEFAULT 'outbound',
  `extra_info` text COLLATE utf8mb4_general_ci,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uniq_provider_call` (`provider`,`uniqueid`),
  KEY `idx_calldate` (`calldate`),
  KEY `idx_src` (`src`),
  KEY `idx_dst` (`dst`),
  KEY `idx_disposition` (`disposition`)
) ENGINE=InnoDB AUTO_INCREMENT=22 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `crm_cdr`
--

LOCK TABLES `crm_cdr` WRITE;
/*!40000 ALTER TABLE `crm_cdr` DISABLE KEYS */;
INSERT INTO `crm_cdr` VALUES (1,'issabel','call-apex-0-1795201131','2026-11-21 00:28:51','102','9811001100','Sales Executive <104>','','','',225,213,'ANSWERED','','outbound',NULL,'2026-11-21 12:28:51','2026-11-21 12:28:51'),(2,'issabel','call-apex-1-1795168731','2026-11-20 15:28:51','101','9811001101','Sales Executive <106>','','','',255,246,'ANSWERED','','outbound',NULL,'2026-11-21 12:28:51','2026-11-21 12:28:51'),(3,'issabel','call-apex-2-1795179531','2026-11-20 18:28:51','103','9811001102','Sales Executive <102>','','','',248,233,'ANSWERED','','outbound',NULL,'2026-11-21 12:28:51','2026-11-21 12:28:51'),(4,'issabel','call-apex-3-1795186731','2026-11-20 20:28:51','101','9811001103','Sales Executive <103>','','','',197,183,'ANSWERED','','outbound',NULL,'2026-11-21 12:28:51','2026-11-21 12:28:51'),(5,'issabel','call-apex-4-1795215531','2026-11-21 04:28:51','105','9811001104','Sales Executive <106>','','','',94,84,'ANSWERED','','outbound',NULL,'2026-11-21 12:28:51','2026-11-21 12:28:51'),(6,'issabel','call-apex-5-1795154331','2026-11-20 11:28:51','105','9811001105','Sales Executive <104>','','','',296,288,'ANSWERED','','outbound',NULL,'2026-11-21 12:28:51','2026-11-21 12:28:51'),(7,'issabel','call-apex-6-1795179531','2026-11-20 18:28:51','103','9811001106','Sales Executive <103>','','','',95,86,'ANSWERED','','outbound',NULL,'2026-11-21 12:28:51','2026-11-21 12:28:51'),(8,'issabel','call-apex-7-1795208331','2026-11-21 02:28:51','102','9811001107','Sales Executive <106>','','','',451,440,'ANSWERED','','outbound',NULL,'2026-11-21 12:28:51','2026-11-21 12:28:51'),(9,'issabel','call-apex-8-1795107531','2026-11-19 22:28:51','102','9811001108','Sales Executive <101>','','','',148,136,'ANSWERED','','outbound',NULL,'2026-11-21 12:28:51','2026-11-21 12:28:51'),(10,'issabel','call-apex-9-1795226331','2026-11-21 07:28:51','106','9811001109','Sales Executive <105>','','','',121,109,'ANSWERED','','outbound',NULL,'2026-11-21 12:28:51','2026-11-21 12:28:51'),(11,'issabel','call-apex-10-1795175931','2026-11-20 17:28:51','106','9811001110','Sales Executive <104>','','','',283,270,'ANSWERED','','outbound',NULL,'2026-11-21 12:28:51','2026-11-21 12:28:51'),(12,'issabel','call-apex-11-1795139931','2026-11-20 07:28:51','106','9811001111','Sales Executive <105>','','','',34,19,'VOICEMAIL','','outbound',NULL,'2026-11-21 12:28:51','2026-11-21 12:28:51'),(13,'issabel','call-apex-12-1795229931','2026-11-21 08:28:51','105','9811001112','Sales Executive <101>','','','',397,387,'ANSWERED','','outbound',NULL,'2026-11-21 12:28:51','2026-11-21 12:28:51'),(14,'issabel','call-apex-13-1795085931','2026-11-19 16:28:51','102','9811001113','Sales Executive <102>','','','',361,352,'ANSWERED','','outbound',NULL,'2026-11-21 12:28:51','2026-11-21 12:28:51'),(15,'issabel','call-apex-14-1795150731','2026-11-20 10:28:51','104','9811001114','Sales Executive <101>','','','',119,112,'ANSWERED','','outbound',NULL,'2026-11-21 12:28:51','2026-11-21 12:28:51'),(16,'issabel','CALLFACEFC5983C0','2026-11-21 12:47:50','101','9820111043','','','','',0,0,'INITIATED','','outbound','Connection attempt note: HTTPConnectionPool(host=\'127.0.0.1\', port=8088): Max retries exceeded with url: /ari?src_ext=101&dst_num=9820111043 (Caused by NewConnectionError(\"HTTPConnection(host=\'127.0.0.1\', port=8088): Failed to establish a new connection: [Errno 61] Connection refused\"))','2026-11-21 12:47:50','2026-11-21 12:47:50'),(17,'issabel','CALL9E06F4F4D450','2026-11-21 12:47:58','101','9820111043','','','','',0,0,'INITIATED','','outbound','Connection attempt note: HTTPConnectionPool(host=\'127.0.0.1\', port=8088): Max retries exceeded with url: /ari?src_ext=101&dst_num=9820111043 (Caused by NewConnectionError(\"HTTPConnection(host=\'127.0.0.1\', port=8088): Failed to establish a new connection: [Errno 61] Connection refused\"))','2026-11-21 12:47:58','2026-11-21 12:47:58'),(18,'issabel','CALL3837890FDF77','2026-11-21 12:48:00','101','9820111043','','','','',0,0,'INITIATED','','outbound','Connection attempt note: HTTPConnectionPool(host=\'127.0.0.1\', port=8088): Max retries exceeded with url: /ari?src_ext=101&dst_num=9820111043 (Caused by NewConnectionError(\"HTTPConnection(host=\'127.0.0.1\', port=8088): Failed to establish a new connection: [Errno 61] Connection refused\"))','2026-11-21 12:48:00','2026-11-21 12:48:00'),(19,'issabel','CALL7FDD31A5E67A','2026-11-21 12:48:01','101','9820111031','','','','',0,0,'INITIATED','','outbound','Connection attempt note: HTTPConnectionPool(host=\'127.0.0.1\', port=8088): Max retries exceeded with url: /ari?src_ext=101&dst_num=9820111031 (Caused by NewConnectionError(\"HTTPConnection(host=\'127.0.0.1\', port=8088): Failed to establish a new connection: [Errno 61] Connection refused\"))','2026-11-21 12:48:01','2026-11-21 12:48:01'),(20,'issabel','CALL8FF11E0FEA58','2026-11-21 12:48:03','101','9820111023','','','','',0,0,'INITIATED','','outbound','Connection attempt note: HTTPConnectionPool(host=\'127.0.0.1\', port=8088): Max retries exceeded with url: /ari?src_ext=101&dst_num=9820111023 (Caused by NewConnectionError(\"HTTPConnection(host=\'127.0.0.1\', port=8088): Failed to establish a new connection: [Errno 61] Connection refused\"))','2026-11-21 12:48:03','2026-11-21 12:48:03'),(21,'issabel','CALL3B99CD215D34','2026-11-21 12:48:04','101','9820111039','','','','',0,0,'INITIATED','','outbound','Connection attempt note: HTTPConnectionPool(host=\'127.0.0.1\', port=8088): Max retries exceeded with url: /ari?src_ext=101&dst_num=9820111039 (Caused by NewConnectionError(\"HTTPConnection(host=\'127.0.0.1\', port=8088): Failed to establish a new connection: [Errno 61] Connection refused\"))','2026-11-21 12:48:04','2026-11-21 12:48:04');
/*!40000 ALTER TABLE `crm_cdr` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `designations`
--

DROP TABLE IF EXISTS `designations`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `designations` (
  `id` int NOT NULL AUTO_INCREMENT,
  `designation_uuid` varchar(40) COLLATE utf8mb4_general_ci NOT NULL,
  `designation_name` varchar(100) COLLATE utf8mb4_general_ci NOT NULL,
  `status` tinyint(1) NOT NULL DEFAULT '1',
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `designation_uuid` (`designation_uuid`)
) ENGINE=InnoDB AUTO_INCREMENT=8 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `designations`
--

LOCK TABLES `designations` WRITE;
/*!40000 ALTER TABLE `designations` DISABLE KEYS */;
INSERT INTO `designations` VALUES (1,'95bb8a2c-ce65-4a13-8dca-0531c2e5d010','Sales Manager',1,'2026-11-21 06:45:29','2026-11-21 06:45:29'),(2,'ac6251c2-b625-4e8e-bc37-a6810f241eee','Senior Sales Executive',1,'2026-11-21 06:45:29','2026-11-21 06:45:29'),(3,'fa01036c-1a72-494a-852d-78bdb5dafdf9','Business Development Executive',1,'2026-11-21 06:45:29','2026-11-21 06:45:29'),(4,'2e5d85c7-0947-4c90-9f72-46b4965db0db','Team Leader',1,'2026-11-21 06:45:29','2026-11-21 06:45:29'),(5,'c5170098-5a75-4ddc-834f-f62bfbb50c0e','Customer Support Executive',1,'2026-11-21 06:45:29','2026-11-21 06:45:29'),(6,'089fb15f-1b30-4ad8-9199-a74896e077c5','Sales Director',1,'2026-11-21 06:58:51','2026-11-21 06:58:51'),(7,'784d7d1d-3992-4266-b898-69349b394e52','Relationship Manager',1,'2026-11-21 06:58:51','2026-11-21 06:58:51');
/*!40000 ALTER TABLE `designations` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `email_attachments`
--

DROP TABLE IF EXISTS `email_attachments`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `email_attachments` (
  `id` int NOT NULL AUTO_INCREMENT,
  `attachment_uuid` varchar(50) COLLATE utf8mb4_general_ci NOT NULL,
  `email_id` int NOT NULL,
  `email_uuid` varchar(50) COLLATE utf8mb4_general_ci NOT NULL,
  `file_name` varchar(255) COLLATE utf8mb4_general_ci NOT NULL,
  `file_path` varchar(500) COLLATE utf8mb4_general_ci NOT NULL,
  `file_size` int DEFAULT '0',
  `file_type` varchar(100) COLLATE utf8mb4_general_ci DEFAULT '',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `attachment_uuid` (`attachment_uuid`),
  KEY `idx_email_id` (`email_id`),
  KEY `idx_email_uuid` (`email_uuid`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `email_attachments`
--

LOCK TABLES `email_attachments` WRITE;
/*!40000 ALTER TABLE `email_attachments` DISABLE KEYS */;
/*!40000 ALTER TABLE `email_attachments` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `emails`
--

DROP TABLE IF EXISTS `emails`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `emails` (
  `id` int NOT NULL AUTO_INCREMENT,
  `email_uuid` varchar(30) COLLATE utf8mb4_general_ci NOT NULL,
  `user_id` int DEFAULT NULL,
  `sender_email` longtext COLLATE utf8mb4_general_ci NOT NULL,
  `sender_name` longtext COLLATE utf8mb4_general_ci,
  `recipient_email` longtext COLLATE utf8mb4_general_ci,
  `recipient_name` longtext COLLATE utf8mb4_general_ci,
  `cc_email` longtext COLLATE utf8mb4_general_ci,
  `bcc_email` longtext COLLATE utf8mb4_general_ci,
  `subject` varchar(500) COLLATE utf8mb4_general_ci NOT NULL,
  `body_html` longtext COLLATE utf8mb4_general_ci,
  `body_plain` longtext COLLATE utf8mb4_general_ci,
  `folder` enum('inbox','sent','drafts','trash') COLLATE utf8mb4_general_ci NOT NULL DEFAULT 'inbox',
  `is_starred` tinyint(1) NOT NULL DEFAULT '0',
  `is_read` tinyint(1) NOT NULL DEFAULT '0',
  `is_deleted` tinyint(1) NOT NULL DEFAULT '0',
  `parent_email_id` int DEFAULT NULL,
  `lead_id` int DEFAULT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `email_uuid` (`email_uuid`),
  KEY `idx_folder` (`folder`),
  KEY `idx_user_id` (`user_id`),
  KEY `idx_created_at` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `emails`
--

LOCK TABLES `emails` WRITE;
/*!40000 ALTER TABLE `emails` DISABLE KEYS */;
/*!40000 ALTER TABLE `emails` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `extensions`
--

DROP TABLE IF EXISTS `extensions`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `extensions` (
  `id` int NOT NULL AUTO_INCREMENT,
  `extension_uuid` varchar(20) COLLATE utf8mb4_general_ci NOT NULL,
  `calling_api_id` int NOT NULL,
  `extension_number` int NOT NULL,
  `status` tinyint NOT NULL DEFAULT '1',
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `extension_password` varchar(100) COLLATE utf8mb4_general_ci DEFAULT NULL,
  `account_id` varchar(100) COLLATE utf8mb4_general_ci DEFAULT NULL,
  `did_number` varchar(50) COLLATE utf8mb4_general_ci DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `extension_uuid` (`extension_uuid`),
  UNIQUE KEY `extension_number` (`extension_number`)
) ENGINE=InnoDB AUTO_INCREMENT=8 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `extensions`
--

LOCK TABLES `extensions` WRITE;
/*!40000 ALTER TABLE `extensions` DISABLE KEYS */;
INSERT INTO `extensions` VALUES (1,'25bf1d88-b2eb-4929-9',1,101,1,'2026-11-21 06:58:51','pass101',NULL,'+918049000101'),(2,'b90a12fb-d8da-49a0-8',1,102,1,'2026-11-21 06:58:51','pass102',NULL,'+918049000102'),(3,'b79c20d6-fd07-41f5-8',1,103,1,'2026-11-21 06:58:51','pass103',NULL,'+918049000103'),(4,'14461c7a-f74e-4138-b',1,104,1,'2026-11-21 06:58:51','pass104',NULL,'+918049000104'),(5,'5547eb47-4153-409d-b',1,105,1,'2026-11-21 06:58:51','pass105',NULL,'+918049000105'),(6,'120d53b2-bbb1-449e-b',1,106,1,'2026-11-21 06:58:51','pass106',NULL,'+918049000106'),(7,'3dd43f58-4902-478d-a',1,107,1,'2026-11-21 06:58:51','pass107',NULL,'+918049000107');
/*!40000 ALTER TABLE `extensions` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `followups`
--

DROP TABLE IF EXISTS `followups`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `followups` (
  `id` int NOT NULL AUTO_INCREMENT,
  `followup_uuid` varchar(40) COLLATE utf8mb4_general_ci NOT NULL,
  `lead_id` int NOT NULL,
  `created_by_user_id` int NOT NULL,
  `followup_date` datetime NOT NULL,
  `followup_type` varchar(60) COLLATE utf8mb4_general_ci DEFAULT NULL,
  `followup_status` varchar(40) COLLATE utf8mb4_general_ci NOT NULL DEFAULT 'pending',
  `notes` text COLLATE utf8mb4_general_ci,
  `completed_at` datetime DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `created_by_name` varchar(255) COLLATE utf8mb4_general_ci DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_followups_uuid` (`followup_uuid`),
  KEY `idx_followups_lead_id` (`lead_id`),
  KEY `idx_followups_user_id` (`created_by_user_id`),
  KEY `idx_followups_date` (`followup_date`),
  KEY `idx_followups_status` (`followup_status`),
  CONSTRAINT `fk_followups_lead` FOREIGN KEY (`lead_id`) REFERENCES `leads` (`id`),
  CONSTRAINT `fk_followups_user` FOREIGN KEY (`created_by_user_id`) REFERENCES `users` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=9 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `followups`
--

LOCK TABLES `followups` WRITE;
/*!40000 ALTER TABLE `followups` DISABLE KEYS */;
INSERT INTO `followups` VALUES (1,'2e376c51-dfe2-4b48-a102-1ff9cc7160a4',3,1,'2026-11-21 15:15:30','Call','pending','Discuss strategy results',NULL,'2026-11-21 12:15:29','2026-11-21 12:15:29','System Administrator'),(2,'e9df775c-50ca-414a-9d4b-068e6cbdc823',8,1,'2026-11-22 14:15:30','Call','pending','Followup on discount request',NULL,'2026-11-21 12:15:29','2026-11-21 12:15:29','System Administrator'),(3,'2281ef82-85a8-429a-a0ac-1691fe556794',2,1,'2026-11-21 17:15:30','WhatsApp','pending','Share client testimonials',NULL,'2026-11-21 12:15:29','2026-11-21 12:15:29','System Administrator'),(4,'31364621-af45-4b7f-8599-f2c1e35b55e0',9,1,'2026-11-23 12:15:30','Email','pending','Send commodity market brief',NULL,'2026-11-21 12:15:29','2026-11-21 12:15:29','System Administrator'),(5,'869d500d-f53a-426b-a67c-9d4c5417de1a',4,1,'2026-11-21 16:28:51','Call','pending','Clarify commodity risk and trade margin requirements',NULL,'2026-11-21 12:28:51','2026-11-21 12:28:51','System Administrator'),(6,'69a65979-3d06-4202-9095-54ad58c4569d',14,1,'2026-11-23 12:28:51','WhatsApp','pending','Payment follow-up before the new expiry cycle begins',NULL,'2026-11-21 12:28:51','2026-11-21 12:28:51','System Administrator'),(7,'b805ff45-920e-4994-9bfc-800b3baa1a99',13,1,'2026-11-24 12:28:51','Meeting','pending','Corporate office presentation for treasury board',NULL,'2026-11-21 12:28:51','2026-11-21 12:28:51','System Administrator'),(8,'fe41b54e-f935-4a23-906d-f63b8b3a1378',15,1,'2026-11-21 17:28:51','Demo','pending','Walkthrough of algorithmic execution terminal',NULL,'2026-11-21 12:28:51','2026-11-21 12:28:51','System Administrator');
/*!40000 ALTER TABLE `followups` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `free_trials`
--

DROP TABLE IF EXISTS `free_trials`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `free_trials` (
  `id` int NOT NULL AUTO_INCREMENT,
  `free_trial_uuid` varchar(40) COLLATE utf8mb4_general_ci NOT NULL,
  `lead_id` int NOT NULL,
  `created_by_user_id` int NOT NULL,
  `trial_name` varchar(160) COLLATE utf8mb4_general_ci DEFAULT NULL,
  `start_date` datetime DEFAULT NULL,
  `end_date` datetime DEFAULT NULL,
  `trial_status` varchar(40) COLLATE utf8mb4_general_ci NOT NULL DEFAULT 'active',
  `notes` text COLLATE utf8mb4_general_ci,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `created_by_name` varchar(255) COLLATE utf8mb4_general_ci DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_free_trials_uuid` (`free_trial_uuid`),
  KEY `idx_free_trials_lead_id` (`lead_id`),
  KEY `idx_free_trials_user_id` (`created_by_user_id`),
  KEY `idx_free_trials_status` (`trial_status`),
  CONSTRAINT `fk_free_trials_lead` FOREIGN KEY (`lead_id`) REFERENCES `leads` (`id`),
  CONSTRAINT `fk_free_trials_user` FOREIGN KEY (`created_by_user_id`) REFERENCES `users` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `free_trials`
--

LOCK TABLES `free_trials` WRITE;
/*!40000 ALTER TABLE `free_trials` DISABLE KEYS */;
INSERT INTO `free_trials` VALUES (1,'a29d1319-2343-4f66-b9c9-cc83c80ea88f',4,1,'3-Day Equity Trial','2026-11-20 12:15:30','2026-11-23 12:15:30','active','Started via portal','2026-11-21 12:15:29','2026-11-21 12:15:29','System Administrator'),(2,'c02afb2c-f288-4669-ac7c-6dffb23c304e',2,1,'Intraday Options Trial','2026-11-21 12:15:30','2026-11-24 12:15:30','active','Started via portal','2026-11-21 12:15:29','2026-11-21 12:15:29','System Administrator');
/*!40000 ALTER TABLE `free_trials` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `handbooks`
--

DROP TABLE IF EXISTS `handbooks`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `handbooks` (
  `id` int NOT NULL AUTO_INCREMENT,
  `handbook_uuid` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `title` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `category` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT 'General',
  `description` longtext COLLATE utf8mb4_unicode_ci NOT NULL,
  `created_by_user_id` int DEFAULT NULL,
  `created_by_name` varchar(150) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `status` tinyint(1) DEFAULT '1',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `handbook_uuid` (`handbook_uuid`),
  KEY `idx_category` (`category`),
  KEY `idx_status` (`status`)
) ENGINE=InnoDB AUTO_INCREMENT=5 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `handbooks`
--

LOCK TABLES `handbooks` WRITE;
/*!40000 ALTER TABLE `handbooks` DISABLE KEYS */;
INSERT INTO `handbooks` VALUES (1,'ecb1a916-ea06-4aa3-a3e8-1adfd1b3f192','High-Intent Lead Qualification Framework (BANT)','Sales Playbook','### Overview\nThe BANT framework ensures our sales reps spend time on prospects with genuine transaction readiness.\n\n1. **Budget**: Confirm whether the investor allocates a minimum of ₹2-5 Lakhs for equity/options trading.\n2. **Authority**: Verify whether the prospect is the direct decision-maker or requires approval from a partner/family office.\n3. **Need**: Understand their pain point (lack of time, prior trading losses, inconsistent strategy execution).\n4. **Timeline**: Establish when they intend to begin trading live calls (e.g. this week vs next month).',1,'System Administrator',1,'2026-11-21 12:28:51','2026-11-21 12:28:51'),(2,'614e890d-8233-41a4-b124-99f0faba7bd4','Objection Handling Guide: Pricing & Competitor Fees','Objection Handling','### Key Objection: \"Your advisory fee is higher than Telegram/Discount tipsters.\"\n\n**How to Respond:**\n- Acknowledge their perspective: *\"I completely understand that price is an important factor.\"*\n- Highlight SEBI Compliance: *\"Unlike unverified Telegram channels, we are a SEBI-registered advisory operating under strict audit standards and documented track records.\"*\n- Position as Risk Management: *\"A single poor trade without a stop-loss can cost much more than our entire quarterly advisory subscription. We protect your capital first.\"*',1,'System Administrator',1,'2026-11-21 12:28:51','2026-11-21 12:28:51'),(3,'484aeacb-d5d7-46d1-9438-8b3c81656914','Sales Follow-up Cadence & Best Practices','Best Practices','### Standard 7-Day Follow-up Cycle\n- **Day 1**: Initial discovery call + WhatsApp introduction card.\n- **Day 2**: Email performance report and client testimonial deck.\n- **Day 4**: Mid-week market update call sharing recent successful trade recap.\n- **Day 7**: Proposal review call with limited-time quarterly fee benefit.',1,'System Administrator',1,'2026-11-21 12:28:51','2026-11-21 12:28:51'),(4,'b9428865-84f2-4e3f-987b-7e3dfffbe651','CRM Daily Routine for Sales Executives','Operations','### Daily Morning Checklist (9:00 AM - 10:00 AM)\n1. Open CRM Dashboard and check pending follow-ups for today.\n2. Prioritize clients with proposal status over cold leads.\n3. Review yesterday\'s call history and update disposition notes.\n4. Verify all payment receipts are attached to sales orders before submitting for approval.',1,'System Administrator',1,'2026-11-21 12:28:51','2026-11-21 12:28:51');
/*!40000 ALTER TABLE `handbooks` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `lead_activities`
--

DROP TABLE IF EXISTS `lead_activities`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `lead_activities` (
  `id` int NOT NULL AUTO_INCREMENT,
  `activity_uuid` varchar(50) COLLATE utf8mb4_general_ci NOT NULL,
  `lead_id` int NOT NULL,
  `user_id` int DEFAULT NULL,
  `action_type` varchar(100) COLLATE utf8mb4_general_ci NOT NULL,
  `status_id` varchar(50) COLLATE utf8mb4_general_ci DEFAULT NULL,
  `status_name` varchar(100) COLLATE utf8mb4_general_ci DEFAULT NULL,
  `comment` text COLLATE utf8mb4_general_ci,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `activity_uuid` (`activity_uuid`),
  KEY `idx_lead_id` (`lead_id`),
  KEY `idx_lead_activities_user_action_created` (`user_id`,`action_type`,`created_at`)
) ENGINE=InnoDB AUTO_INCREMENT=26 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `lead_activities`
--

LOCK TABLES `lead_activities` WRITE;
/*!40000 ALTER TABLE `lead_activities` DISABLE KEYS */;
INSERT INTO `lead_activities` VALUES (1,'3ac2fe9b-8eea-4553-8647-9d0ca808b199',1,1,'status_change','1','New Lead','Looking for equity stock options advisory','2026-11-21 12:28:51'),(2,'287b0f22-595d-43a3-8af2-cee0daa33701',2,2,'status_change','2','Interested','Wants performance report and fee details','2026-11-20 12:28:51'),(3,'1add65e0-24a2-44c2-9855-68c722751159',3,3,'status_change','3','Follow Up','Call scheduled for discussion on portfolio size','2026-11-19 12:28:51'),(4,'a37d7c78-532d-4a4a-bcb7-7aa122032f07',4,4,'status_change','9','Under Discussion','Requested detailed comparison between equity vs options','2026-11-18 12:28:51'),(5,'b4cb7c90-c907-445e-b2b6-b28ca54d820e',5,5,'status_change','5','Proposal Sent','Sent annual package invoice with GST calculation','2026-11-17 12:28:51'),(6,'ae802ab5-1388-4123-95b6-9193ba8019cd',6,6,'status_change','6','Converted / Won','Payment approved via UPI. Onboarding client profile created.','2026-11-16 12:28:51'),(7,'9e1842e5-0840-41a0-b771-58190699d628',7,1,'status_change','6','Converted / Won','Joined HNI wealth advisory plan. Dedicated RM assigned.','2026-11-15 12:28:51'),(8,'e403654d-496b-4357-9ec2-cb11b426bd5a',8,2,'status_change','3','Follow Up','Discussing plan with family accountant, requested callback','2026-11-14 12:28:51'),(9,'d025bac8-d91c-42bf-be84-0b3b36c6ae0a',9,3,'status_change','2','Interested','Active commodities trader looking for MCX bullion calls','2026-11-13 12:28:51'),(10,'4a218c40-0de6-48aa-b2c3-f8b6f1ef0488',10,4,'status_change','6','Converted / Won','Quarterly plan subscribed via Credit Card. KYC completed.','2026-11-12 12:28:51'),(11,'5ecee84f-ac23-45b9-93ad-a84bde22afb5',11,5,'status_change','1','New Lead','Fresh inquiry submitted on website form regarding swing advisory','2026-11-11 12:28:51'),(12,'4fa4984f-1807-4104-9df4-ad1b501efb23',12,6,'status_change','7','Not Interested','Currently not active in equity market, asked to check back next quarter','2026-11-10 12:28:51'),(13,'08489b9c-4709-4b1f-a331-2220c1aa1b03',13,1,'status_change','5','Proposal Sent','Corporate treasury manager seeking institutional advisory rate card','2026-11-09 12:28:51'),(14,'6b0498f6-d081-4135-8840-7b71c3889e4b',14,2,'status_change','3','Follow Up','Interested in commodity options, promised payment confirmation by Friday','2026-11-08 12:28:51'),(15,'f14e71b6-f275-417a-a32d-ead9b61dd395',15,3,'status_change','2','Interested','Wants demo of real-time signals dashboard before making payment','2026-11-21 12:28:51'),(16,'2747c096-8d44-4ac5-93f7-8e31bb47b76a',16,4,'status_change','1','New Lead','Downloaded market trends whitepaper, waiting for initial callback','2026-11-20 12:28:51'),(17,'f1e7de44-9aeb-4cb8-88eb-5c8ad1da76e1',17,5,'status_change','6','Converted / Won','Opted for Options & Futures plan. Invoice paid via NetBanking.','2026-11-19 12:28:51'),(18,'6beace1c-edf5-4c27-af6c-949322ec4a9a',18,6,'status_change','8','Lost','Opted for discount broker self-trade package','2026-11-18 12:28:51'),(19,'ACTB6D57513704C',61,1,'Click to Call',NULL,'No Status','Initiated click-to-call to lead 61','2026-11-21 12:47:50'),(20,'ACT9A8E1ADE92BA',61,1,'Click to Call',NULL,'No Status','Initiated click-to-call to lead 61','2026-11-21 12:47:58'),(21,'ACTD4D61CA0DE81',61,1,'Click to Call',NULL,'No Status','Initiated click-to-call to lead 61','2026-11-21 12:48:00'),(22,'ACT8D86A331D920',49,1,'Click to Call',NULL,'No Status','Initiated click-to-call to lead 49','2026-11-21 12:48:01'),(23,'ACT4ADED106AA4D',41,1,'Click to Call',NULL,'No Status','Initiated click-to-call to lead 41','2026-11-21 12:48:03'),(24,'ACT55EE270DE542',57,1,'Click to Call',NULL,'No Status','Initiated click-to-call to lead 57','2026-11-21 12:48:04'),(25,'ACTC3E6DEFA4321',61,1,'Status & Comment Updated',NULL,'Interested',NULL,'2026-11-21 12:49:41');
/*!40000 ALTER TABLE `lead_activities` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `lead_batch_items`
--

DROP TABLE IF EXISTS `lead_batch_items`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `lead_batch_items` (
  `id` int NOT NULL AUTO_INCREMENT,
  `item_uuid` varchar(40) COLLATE utf8mb4_general_ci NOT NULL,
  `batch_id` int DEFAULT NULL,
  `row_number` int NOT NULL,
  `name` varchar(160) COLLATE utf8mb4_general_ci DEFAULT NULL,
  `mobile_number` varchar(255) COLLATE utf8mb4_general_ci DEFAULT NULL,
  `email` varchar(160) COLLATE utf8mb4_general_ci DEFAULT NULL,
  `address` text COLLATE utf8mb4_general_ci,
  `item_status` enum('fresh','duplicate','invalid','imported') COLLATE utf8mb4_general_ci NOT NULL,
  `validation_message` varchar(255) COLLATE utf8mb4_general_ci DEFAULT NULL,
  `duplicate_lead_id` int DEFAULT NULL,
  `duplicate_lifecycle_status` varchar(60) COLLATE utf8mb4_general_ci DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `item_uuid` (`item_uuid`),
  KEY `idx_batch_items_status` (`item_status`),
  KEY `idx_batch_items_mobile` (`mobile_number`)
) ENGINE=InnoDB AUTO_INCREMENT=44 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `lead_batch_items`
--

LOCK TABLES `lead_batch_items` WRITE;
/*!40000 ALTER TABLE `lead_batch_items` DISABLE KEYS */;
INSERT INTO `lead_batch_items` VALUES (1,'LBI7EE7E1D96F16E82E',4,1,'Aarav Sharma','9820111001','aarav.sharma@nortrade.example','','imported','',NULL,NULL,'2026-11-21 12:47:32'),(2,'LBI795E8FDB0A052E94',4,2,'Diya Patel','9820111002','diya.patel@vertexbuild.example','','imported','',NULL,NULL,'2026-11-21 12:47:32'),(3,'LBI0D0D07059FD4C085',4,3,'Rohan Verma','9820111003','rohan.verma@skylinearch.example','','imported','',NULL,NULL,'2026-11-21 12:47:32'),(4,'LBIB6FD9D78E8121F72',4,4,'Ananya Iyer','9820111004','ananya.iyer@studioiyer.example','','imported','',NULL,NULL,'2026-11-21 12:47:32'),(5,'LBI3BD24D5363143542',4,5,'Vikramaditya Rao','9820111005','vikram.rao@raodesign.example','','imported','',NULL,NULL,'2026-11-21 12:47:32'),(6,'LBI05B0066D0A1BA5A1',4,6,'Meera Krishnan','9820111006','meera.k@krishnanassociates.example','','imported','',NULL,NULL,'2026-11-21 12:47:32'),(7,'LBIBD7AAC02BF53DF71',4,7,'Kabir Malhotra','9820111007','kabir.m@malhotradev.example','','imported','',NULL,NULL,'2026-11-21 12:47:32'),(8,'LBI7BB645CD1CAFED3D',4,8,'Ishita Joshi','9820111008','ishita.joshi@joshiplanners.example','','imported','',NULL,NULL,'2026-11-21 12:47:32'),(9,'LBIDCFC60C3158BA909',4,9,'Siddharth Menon','9820111009','siddharth.menon@menoninfra.example','','imported','',NULL,NULL,'2026-11-21 12:47:32'),(10,'LBI0C92EFC3D90213D5',4,10,'Kavya Nair','9820111010','kavya.nair@atelierkavya.example','','imported','',NULL,NULL,'2026-11-21 12:47:32'),(11,'LBIA9C9B41C024EF171',4,11,'Arjun Kapoor','9820111011','arjun.kapoor@kapoorconstructions.example','','imported','',NULL,NULL,'2026-11-21 12:47:32'),(12,'LBI3A983AD4F2704159',4,12,'Nandini Kulkarni','9820111012','nandini.k@kulkarnistudio.example','','imported','',NULL,NULL,'2026-11-21 12:47:32'),(13,'LBIBF2A92690AE8921C',4,13,'Pranav Desai','9820111013','pranav.desai@desaibuilders.example','','imported','',NULL,NULL,'2026-11-21 12:47:32'),(14,'LBICBE71762947456DF',4,14,'Tara Chatterjee','9820111014','tara.c@chatterjeearch.example','','imported','',NULL,NULL,'2026-11-21 12:47:32'),(15,'LBI89E9C9CC62A8DC05',4,15,'Rishabh Gupta','9820111015','rishabh.gupta@guptarealty.example','','imported','',NULL,NULL,'2026-11-21 12:47:32'),(16,'LBI7C877934A3A9BFD8',4,16,'Pooja Hegde','9820111016','pooja.hegde@hegdespaces.example','','imported','',NULL,NULL,'2026-11-21 12:47:32'),(17,'LBI4CA5904EAF3665A0',4,17,'Aditya Bansal','9820111017','aditya.bansal@bansalgroup.example','','imported','',NULL,NULL,'2026-11-21 12:47:32'),(18,'LBIBDD98ECADDF8CC03',4,18,'Sneha Choudhury','9820111018','sneha.c@choudhurydesign.example','','imported','',NULL,NULL,'2026-11-21 12:47:32'),(19,'LBI75EE49CC2775C4E2',4,19,'Karanbir Gill','9820111019','karanbir.gill@gillinfra.example','','imported','',NULL,NULL,'2026-11-21 12:47:32'),(20,'LBI11B824F8EDAC3B17',4,20,'Shruti Agarwal','9820111020','shruti.agarwal@agarwalarch.example','','imported','',NULL,NULL,'2026-11-21 12:47:32'),(21,'LBI2CB11FF6C8167304',4,21,'Nikhil Tiwari','9820111021','nikhil.tiwari@tiwariprojects.example','','imported','',NULL,NULL,'2026-11-21 12:47:32'),(22,'LBI3F6136B46875AB1B',4,22,'Ritika Sen','9820111022','ritika.sen@seninteriors.example','','imported','',NULL,NULL,'2026-11-21 12:47:32'),(23,'LBI3F12B69404FA5230',4,23,'Varun Mishra','9820111023','varun.mishra@mishradevelopers.example','','imported','',NULL,NULL,'2026-11-21 12:47:32'),(24,'LBIB0C7BFF2813B54A3',4,24,'Aishwarya Pillai','9820111024','aishwarya.p@pillaistudio.example','','imported','',NULL,NULL,'2026-11-21 12:47:32'),(25,'LBIA4D246AE1CB47AB8',4,25,'Harshvardhan Singh','9820111025','harsh.singh@singhheritage.example','','imported','',NULL,NULL,'2026-11-21 12:47:32'),(26,'LBI1A2B877D90D0A239',4,26,'Divya Shetty','9820111026','divya.shetty@shettybuildtech.example','','imported','',NULL,NULL,'2026-11-21 12:47:32'),(27,'LBI3BE1B249F8E1F4D5',4,27,'Manish Pandey','9820111027','manish.pandey@pandeyestates.example','','imported','',NULL,NULL,'2026-11-21 12:47:32'),(28,'LBIBF12A8181EC6FC3F',4,28,'Preeti Saxena','9820111028','preeti.saxena@saxenadesign.example','','imported','',NULL,NULL,'2026-11-21 12:47:32'),(29,'LBIB34CE92CC04DB50E',4,29,'Yashwanth Reddy','9820111029','yash.reddy@reddyinfra.example','','imported','',NULL,NULL,'2026-11-21 12:47:32'),(30,'LBI5F624E2FBF3D25C4',4,30,'Komal Thakur','9820111030','komal.thakur@thakurspaces.example','','imported','',NULL,NULL,'2026-11-21 12:47:32'),(31,'LBI4D3257DB3F737268',4,31,'Raghavendra Bhat','9820111031','raghav.bhat@bhatarchitects.example','','imported','',NULL,NULL,'2026-11-21 12:47:32'),(32,'LBIBA380BBE0F13D82E',4,32,'Simran Kaur','9820111032','simran.kaur@kaurdevelopments.example','','imported','',NULL,NULL,'2026-11-21 12:47:32'),(33,'LBID291D1B1BD038388',4,33,'Abhishek Dubey','9820111033','abhishek.dubey@dubeyarch.example','','imported','',NULL,NULL,'2026-11-21 12:47:32'),(34,'LBIA21703121918D368',4,34,'Gayatri Menon','9820111034','gayatri.menon@menonstudio.example','','imported','',NULL,NULL,'2026-11-21 12:47:32'),(35,'LBI5A6E4EC72856E3A0',4,35,'Sandeep Yadav','9820111035','sandeep.yadav@yadavrealty.example','','imported','',NULL,NULL,'2026-11-21 12:47:32'),(36,'LBI0AE44778AEBC6360',4,36,'Ankita Mukherjee','9820111036','ankita.m@mukherjeeassociates.example','','imported','',NULL,NULL,'2026-11-21 12:47:32'),(37,'LBIA32EC18BD8AA2CEC',4,37,'Gaurav Chawla','9820111037','gaurav.chawla@chawlabuilders.example','','imported','',NULL,NULL,'2026-11-21 12:47:32'),(38,'LBI5AF25A3B6053C2CD',4,38,'Pallavi Deshmukh','9820111038','pallavi.d@deshmukharch.example','','imported','',NULL,NULL,'2026-11-21 12:47:32'),(39,'LBI4DE49296C0E25CE4',4,39,'Tushar Kulkarni','9820111039','tushar.k@kulkarnigroup.example','','imported','',NULL,NULL,'2026-11-21 12:47:32'),(40,'LBIDE0F2669F6A58EF7',4,40,'Neha Gokhale','9820111040','neha.gokhale@gokhaledesign.example','','imported','',NULL,NULL,'2026-11-21 12:47:32'),(41,'LBI0E54BCFF4EB59F88',4,41,'Rohan Joshi','9820111041','rohan.joshi@joshirealty.example','','imported','',NULL,NULL,'2026-11-21 12:47:32'),(42,'LBI6164174E45C0443D',4,42,'Shraddha Patil','9820111042','shraddha.patil@patilarchitects.example','','imported','',NULL,NULL,'2026-11-21 12:47:32'),(43,'LBI54EB98E5C4349846',4,43,'Vivek Sharma','9820111043','vivek.sharma@sharma','','imported','',NULL,NULL,'2026-11-21 12:47:32');
/*!40000 ALTER TABLE `lead_batch_items` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `lead_batches`
--

DROP TABLE IF EXISTS `lead_batches`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `lead_batches` (
  `id` int NOT NULL AUTO_INCREMENT,
  `batch_uuid` varchar(40) COLLATE utf8mb4_general_ci NOT NULL,
  `batch_name` varchar(160) COLLATE utf8mb4_general_ci NOT NULL,
  `upload_type` enum('file','quick_paste') COLLATE utf8mb4_general_ci NOT NULL,
  `lead_source` int DEFAULT NULL,
  `uploaded_by` varchar(40) COLLATE utf8mb4_general_ci DEFAULT NULL,
  `imported_at` datetime DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `batch_uuid` (`batch_uuid`),
  KEY `idx_lead_batches_uuid` (`batch_uuid`),
  KEY `idx_lead_batches_created_at` (`created_at`),
  KEY `idx_lead_batches_source` (`lead_source`)
) ENGINE=InnoDB AUTO_INCREMENT=5 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `lead_batches`
--

LOCK TABLES `lead_batches` WRITE;
/*!40000 ALTER TABLE `lead_batches` DISABLE KEYS */;
INSERT INTO `lead_batches` VALUES (1,'02fb05ab-d72c-42ec-8c6d-70d45b6af269','Q4 High Net-Worth Investors CSV','file',1,'admin','2026-11-16 12:28:51','2026-11-16 12:28:51','2026-11-21 12:28:51'),(2,'06ee9778-bdbe-4544-a225-aa25a1dcf902','Bangalore Tech Founders Expo','quick_paste',4,'admin','2026-11-16 12:28:51','2026-11-16 12:28:51','2026-11-21 12:28:51'),(3,'599cf3d3-4967-495b-984b-0f76cdee7e28','Website Webinar Registration Oct','file',3,'admin','2026-11-16 12:28:51','2026-11-16 12:28:51','2026-11-21 12:28:51'),(4,'LB84D021878E12','Lead Batch - 21 Nov 2026 12:47 PM','file',2,'fc5bacb0-3f65-4db0-8','2026-11-21 12:47:32','2026-11-21 12:47:32','2026-11-21 12:47:32');
/*!40000 ALTER TABLE `lead_batches` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `lead_call_history`
--

DROP TABLE IF EXISTS `lead_call_history`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `lead_call_history` (
  `id` int NOT NULL AUTO_INCREMENT,
  `call_history_uuid` varchar(40) COLLATE utf8mb4_general_ci NOT NULL,
  `lead_id` int NOT NULL,
  `user_id` int NOT NULL,
  `extension_id` int DEFAULT NULL,
  `calling_api_id` int DEFAULT NULL,
  `extension_number` varchar(20) COLLATE utf8mb4_general_ci DEFAULT NULL,
  `mobile_number` varchar(20) COLLATE utf8mb4_general_ci NOT NULL,
  `call_direction` varchar(20) COLLATE utf8mb4_general_ci NOT NULL DEFAULT 'outgoing',
  `call_status` varchar(30) COLLATE utf8mb4_general_ci NOT NULL DEFAULT 'initiated',
  `api_status_code` int DEFAULT NULL,
  `api_response` text COLLATE utf8mb4_general_ci,
  `final_api_url` text COLLATE utf8mb4_general_ci,
  `called_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `answered_at` datetime DEFAULT NULL,
  `ended_at` datetime DEFAULT NULL,
  `duration` int NOT NULL DEFAULT '0',
  `recording_url` text COLLATE utf8mb4_general_ci,
  PRIMARY KEY (`id`),
  UNIQUE KEY `unique_call_history_uuid` (`call_history_uuid`),
  KEY `lead_id_index` (`lead_id`),
  KEY `user_id_index` (`user_id`),
  KEY `extension_id_index` (`extension_id`),
  KEY `calling_api_id_index` (`calling_api_id`),
  KEY `call_status_index` (`call_status`),
  KEY `called_at_index` (`called_at`)
) ENGINE=InnoDB AUTO_INCREMENT=7 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `lead_call_history`
--

LOCK TABLES `lead_call_history` WRITE;
/*!40000 ALTER TABLE `lead_call_history` DISABLE KEYS */;
INSERT INTO `lead_call_history` VALUES (1,'CALLFACEFC5983C0',61,1,1,1,'101','9820111043','outgoing','initiated',0,'Connection attempt note: HTTPConnectionPool(host=\'127.0.0.1\', port=8088): Max retries exceeded with url: /ari?src_ext=101&dst_num=9820111043 (Caused by NewConnectionError(\"HTTPConnection(host=\'127.0.0.1\', port=8088): Failed to establish a new connection: [Errno 61] Connection refused\"))','http://127.0.0.1:8088/ari?src_ext=101&dst_num=9820111043','2026-11-21 12:47:50',NULL,NULL,0,NULL),(2,'CALL9E06F4F4D450',61,1,1,1,'101','9820111043','outgoing','initiated',0,'Connection attempt note: HTTPConnectionPool(host=\'127.0.0.1\', port=8088): Max retries exceeded with url: /ari?src_ext=101&dst_num=9820111043 (Caused by NewConnectionError(\"HTTPConnection(host=\'127.0.0.1\', port=8088): Failed to establish a new connection: [Errno 61] Connection refused\"))','http://127.0.0.1:8088/ari?src_ext=101&dst_num=9820111043','2026-11-21 12:47:58',NULL,NULL,0,NULL),(3,'CALL3837890FDF77',61,1,1,1,'101','9820111043','outgoing','initiated',0,'Connection attempt note: HTTPConnectionPool(host=\'127.0.0.1\', port=8088): Max retries exceeded with url: /ari?src_ext=101&dst_num=9820111043 (Caused by NewConnectionError(\"HTTPConnection(host=\'127.0.0.1\', port=8088): Failed to establish a new connection: [Errno 61] Connection refused\"))','http://127.0.0.1:8088/ari?src_ext=101&dst_num=9820111043','2026-11-21 12:48:00',NULL,NULL,0,NULL),(4,'CALL7FDD31A5E67A',49,1,1,1,'101','9820111031','outgoing','initiated',0,'Connection attempt note: HTTPConnectionPool(host=\'127.0.0.1\', port=8088): Max retries exceeded with url: /ari?src_ext=101&dst_num=9820111031 (Caused by NewConnectionError(\"HTTPConnection(host=\'127.0.0.1\', port=8088): Failed to establish a new connection: [Errno 61] Connection refused\"))','http://127.0.0.1:8088/ari?src_ext=101&dst_num=9820111031','2026-11-21 12:48:01',NULL,NULL,0,NULL),(5,'CALL8FF11E0FEA58',41,1,1,1,'101','9820111023','outgoing','initiated',0,'Connection attempt note: HTTPConnectionPool(host=\'127.0.0.1\', port=8088): Max retries exceeded with url: /ari?src_ext=101&dst_num=9820111023 (Caused by NewConnectionError(\"HTTPConnection(host=\'127.0.0.1\', port=8088): Failed to establish a new connection: [Errno 61] Connection refused\"))','http://127.0.0.1:8088/ari?src_ext=101&dst_num=9820111023','2026-11-21 12:48:03',NULL,NULL,0,NULL),(6,'CALL3B99CD215D34',57,1,1,1,'101','9820111039','outgoing','initiated',0,'Connection attempt note: HTTPConnectionPool(host=\'127.0.0.1\', port=8088): Max retries exceeded with url: /ari?src_ext=101&dst_num=9820111039 (Caused by NewConnectionError(\"HTTPConnection(host=\'127.0.0.1\', port=8088): Failed to establish a new connection: [Errno 61] Connection refused\"))','http://127.0.0.1:8088/ari?src_ext=101&dst_num=9820111039','2026-11-21 12:48:04',NULL,NULL,0,NULL);
/*!40000 ALTER TABLE `lead_call_history` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `lead_source_limits`
--

DROP TABLE IF EXISTS `lead_source_limits`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `lead_source_limits` (
  `id` int NOT NULL AUTO_INCREMENT,
  `lead_source_limits_uuid` varchar(40) COLLATE utf8mb4_general_ci NOT NULL,
  `source_id` int NOT NULL,
  `role_id` int NOT NULL,
  `pending_lead_limit` int NOT NULL,
  `daily_lead_limit` int NOT NULL,
  `fetch_lead_limit` int NOT NULL,
  `created_by` int DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `lead_source_limits`
--

LOCK TABLES `lead_source_limits` WRITE;
/*!40000 ALTER TABLE `lead_source_limits` DISABLE KEYS */;
/*!40000 ALTER TABLE `lead_source_limits` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `lead_sources`
--

DROP TABLE IF EXISTS `lead_sources`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `lead_sources` (
  `id` int NOT NULL AUTO_INCREMENT,
  `source_uuid` varchar(40) COLLATE utf8mb4_general_ci NOT NULL,
  `source_name` varchar(100) COLLATE utf8mb4_general_ci NOT NULL,
  `status` tinyint NOT NULL DEFAULT '1',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `source_uuid` (`source_uuid`),
  UNIQUE KEY `source_name` (`source_name`)
) ENGINE=InnoDB AUTO_INCREMENT=8 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `lead_sources`
--

LOCK TABLES `lead_sources` WRITE;
/*!40000 ALTER TABLE `lead_sources` DISABLE KEYS */;
INSERT INTO `lead_sources` VALUES (1,'ad66e95d-793f-4335-b2a8-6693b0caa0b5','Google Search Ads',1,'2026-11-21 12:15:29'),(2,'a81f1d9e-b7fd-46ee-b01e-fa0ee2d4679b','Facebook Inbound',1,'2026-11-21 12:15:29'),(3,'6d12ff2b-169e-4ffe-ab2a-ce4858f4a4d8','Website Organic',1,'2026-11-21 12:15:29'),(4,'f8fb2701-4555-452d-b52e-ccc5544b4ba2','LinkedIn Campaign',1,'2026-11-21 12:15:29'),(5,'9254f1f7-b436-4dc1-bcf7-fe541e86b602','Direct Call',1,'2026-11-21 12:15:29'),(6,'a9bcadda-a6c5-4790-a369-ba5b1082a5a4','Referral Network',1,'2026-11-21 12:28:51'),(7,'332d58c9-87f8-412d-81da-225e69e0eed2','Webinar Lead Gen',1,'2026-11-21 12:28:51');
/*!40000 ALTER TABLE `lead_sources` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `lead_statuses`
--

DROP TABLE IF EXISTS `lead_statuses`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `lead_statuses` (
  `id` int NOT NULL AUTO_INCREMENT,
  `status_uuid` varchar(40) COLLATE utf8mb4_general_ci NOT NULL,
  `status_name` varchar(100) COLLATE utf8mb4_general_ci NOT NULL,
  `status_tone` varchar(30) COLLATE utf8mb4_general_ci NOT NULL DEFAULT 'secondary',
  `status` tinyint NOT NULL DEFAULT '1',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `status_uuid` (`status_uuid`),
  UNIQUE KEY `status_name` (`status_name`)
) ENGINE=InnoDB AUTO_INCREMENT=10 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `lead_statuses`
--

LOCK TABLES `lead_statuses` WRITE;
/*!40000 ALTER TABLE `lead_statuses` DISABLE KEYS */;
INSERT INTO `lead_statuses` VALUES (1,'efc17226-41f9-46c7-a29e-7454264b8c90','New Lead','info',1,'2026-11-21 12:15:29','2026-11-21 12:15:29'),(2,'2c1d9ae2-539f-4831-990a-aa83ff003636','Interested','primary',1,'2026-11-21 12:15:29','2026-11-21 12:15:29'),(3,'e8a1a576-3749-48fc-ba0c-889f490fcef6','Follow Up','warning',1,'2026-11-21 12:15:29','2026-11-21 12:15:29'),(4,'b0986a34-4e20-4def-aafd-30d55a484ad8','Free Trial','info',1,'2026-11-21 12:15:29','2026-11-21 12:15:29'),(5,'6e56ebed-237b-4ccc-9d67-2855e26ca2f9','Proposal Sent','warning',1,'2026-11-21 12:15:29','2026-11-21 12:15:29'),(6,'0558f8b1-d9c5-4a8b-b9f1-9ce3ab48cf4d','Converted / Won','success',1,'2026-11-21 12:15:29','2026-11-21 12:15:29'),(7,'cdf1b8b3-4b8c-43a4-85c0-16e3b800f5e9','Not Interested','secondary',1,'2026-11-21 12:15:29','2026-11-21 12:15:29'),(8,'2b852dbd-ac75-448f-82fd-23206d9b09d2','Lost','danger',1,'2026-11-21 12:15:29','2026-11-21 12:15:29'),(9,'956621f5-cfa5-472c-b61c-bbb2c53d1b10','Under Discussion','info',1,'2026-11-21 12:28:51','2026-11-21 12:28:51');
/*!40000 ALTER TABLE `lead_statuses` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `lead_timeline`
--

DROP TABLE IF EXISTS `lead_timeline`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `lead_timeline` (
  `id` int NOT NULL AUTO_INCREMENT,
  `history_uuid` varchar(40) COLLATE utf8mb4_general_ci NOT NULL,
  `lead_id` int NOT NULL,
  `assignment_id` int DEFAULT NULL,
  `action_type` varchar(80) COLLATE utf8mb4_general_ci NOT NULL,
  `old_status` varchar(80) COLLATE utf8mb4_general_ci DEFAULT NULL,
  `new_status` varchar(80) COLLATE utf8mb4_general_ci DEFAULT NULL,
  `action_by` varchar(40) COLLATE utf8mb4_general_ci DEFAULT NULL,
  `from_user_uuid` varchar(40) COLLATE utf8mb4_general_ci DEFAULT NULL,
  `to_user_uuid` varchar(40) COLLATE utf8mb4_general_ci DEFAULT NULL,
  `remark` text COLLATE utf8mb4_general_ci,
  `metadata` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_bin,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `history_uuid` (`history_uuid`),
  KEY `idx_timeline_lead` (`lead_id`),
  KEY `idx_timeline_assignment` (`assignment_id`),
  KEY `idx_timeline_action` (`action_type`),
  CONSTRAINT `lead_timeline_chk_1` CHECK (json_valid(`metadata`))
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `lead_timeline`
--

LOCK TABLES `lead_timeline` WRITE;
/*!40000 ALTER TABLE `lead_timeline` DISABLE KEYS */;
INSERT INTO `lead_timeline` VALUES (1,'LH058868559ADA',61,NULL,'Status Submitted','No Status','Interested','fc5bacb0-3f65-4db0-8',NULL,NULL,NULL,NULL,'2026-11-21 12:49:41');
/*!40000 ALTER TABLE `lead_timeline` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `leads`
--

DROP TABLE IF EXISTS `leads`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `leads` (
  `id` int NOT NULL AUTO_INCREMENT,
  `lead_uuid` varchar(40) COLLATE utf8mb4_general_ci NOT NULL,
  `lead_batch_id` int DEFAULT NULL,
  `name` varchar(160) COLLATE utf8mb4_general_ci DEFAULT NULL,
  `mobile_number` varchar(15) COLLATE utf8mb4_general_ci NOT NULL,
  `email` varchar(160) COLLATE utf8mb4_general_ci DEFAULT NULL,
  `address` text COLLATE utf8mb4_general_ci,
  `state` varchar(100) COLLATE utf8mb4_general_ci DEFAULT NULL,
  `city` varchar(100) COLLATE utf8mb4_general_ci DEFAULT NULL,
  `lead_source` int NOT NULL,
  `lead_status` int DEFAULT NULL,
  `call_status` tinyint NOT NULL DEFAULT '0',
  `is_disposed` tinyint(1) NOT NULL DEFAULT '0',
  `current_owner_user_id` int DEFAULT NULL,
  `assigned_at` datetime DEFAULT NULL,
  `created_by` varchar(40) COLLATE utf8mb4_general_ci DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `comment` longtext COLLATE utf8mb4_general_ci NOT NULL,
  `disposed_by` varchar(40) COLLATE utf8mb4_general_ci DEFAULT NULL,
  `disposed_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `lead_uuid` (`lead_uuid`),
  UNIQUE KEY `uniq_leads_mobile_number` (`mobile_number`),
  KEY `idx_leads_status` (`lead_status`),
  KEY `idx_leads_owner_created` (`current_owner_user_id`,`created_at`),
  KEY `idx_leads_created_at` (`created_at`),
  KEY `idx_leads_source` (`lead_source`)
) ENGINE=InnoDB AUTO_INCREMENT=62 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `leads`
--

LOCK TABLES `leads` WRITE;
/*!40000 ALTER TABLE `leads` DISABLE KEYS */;
INSERT INTO `leads` VALUES (1,'48bdbb3f-af23-4712-82db-7027945b86d3',NULL,'Rajesh Mehta','9811001101','rajesh.mehta@example.com',NULL,'Maharashtra','Mumbai',1,1,0,0,1,'2026-11-21 12:15:29',NULL,'2026-11-21 12:15:29','2026-11-21 12:15:29','Looking for equity stock options advisory',NULL,NULL),(2,'bcdb18c8-0ea1-4f19-9010-8488720fa19a',NULL,'Anita Desai','9811001102','anita.desai@example.com',NULL,'Maharashtra','Pune',2,2,0,0,2,'2026-11-21 12:15:29',NULL,'2026-11-20 12:15:29','2026-11-21 12:15:29','Wants performance report and fee details',NULL,NULL),(3,'5fd07f9e-b4bc-44f3-921d-bd3ebff2baf7',NULL,'Vikram Joshi','9811001103','vikram.j@example.com',NULL,'Karnataka','Bangalore',3,3,0,0,3,'2026-11-21 12:15:29',NULL,'2026-11-19 12:15:29','2026-11-21 12:15:29','Call scheduled tomorrow 3 PM',NULL,NULL),(4,'404cef99-046b-42c9-9c9f-a9fb8bb62dc4',NULL,'Sunita Rao','9811001104','sunita.rao@example.com',NULL,'Telangana','Hyderabad',4,4,0,0,4,'2026-11-21 12:15:29',NULL,'2026-11-18 12:15:29','2026-11-21 12:15:29','Activated 3-day trial pack',NULL,NULL),(5,'d7d61330-d3e4-48bf-8ea0-1365e305a4e5',NULL,'Rohan Malhotra','9811001105','rohan.m@example.com',NULL,'Delhi','Delhi',1,5,0,0,1,'2026-11-21 12:15:29',NULL,'2026-11-17 12:15:29','2026-11-21 12:15:29','Sent annual package invoice',NULL,NULL),(6,'d5eccf22-7994-43a3-b9ed-907b70d37879',NULL,'Manish Kulkarni','9811001106','manish.k@example.com',NULL,'Gujarat','Ahmedabad',5,6,0,0,2,'2026-11-21 12:15:29',NULL,'2026-11-16 12:15:29','2026-11-21 12:15:29','Payment approved via UPI',NULL,NULL),(7,'2b34ef4b-9984-4fa1-965a-0b64906dcca8',NULL,'Pooja Singhania','9811001107','pooja.s@example.com',NULL,'West Bengal','Kolkata',3,6,0,0,3,'2026-11-21 12:15:29',NULL,'2026-11-15 12:15:29','2026-11-21 12:15:29','Joined HNI wealth advisory',NULL,NULL),(8,'59e988dc-d1c5-47fd-9595-4ba90973de91',NULL,'Kavita Nair','9811001108','kavita.nair@example.com',NULL,'Kerala','Kochi',2,3,0,0,4,'2026-11-21 12:15:29',NULL,'2026-11-14 12:15:29','2026-11-21 12:15:29','Discussing with business partner',NULL,NULL),(9,'ae8e60a4-93f5-49fd-a0ec-0ca9da98c8c3',NULL,'Arjun Reddy','9811001109','arjun.reddy@example.com',NULL,'Tamil Nadu','Chennai',4,2,0,0,1,'2026-11-21 12:15:29',NULL,'2026-11-13 12:15:29','2026-11-21 12:15:29','Interested in commodity pack',NULL,NULL),(10,'69682593-199b-44ea-addc-66585d552295',NULL,'Deepak Bansal','9811001110','deepak.b@example.com',NULL,'Rajasthan','Jaipur',5,6,0,0,2,'2026-11-21 12:15:29',NULL,'2026-11-12 12:15:29','2026-11-21 12:15:29','Quarterly plan subscribed',NULL,NULL),(11,'425fb75a-b681-4a95-a089-c273bae73e16',NULL,'Neha Gupta','9811001111','neha.gupta@example.com',NULL,'Punjab','Chandigarh',1,1,0,0,3,'2026-11-21 12:15:29',NULL,'2026-11-11 12:15:29','2026-11-21 12:15:29','Inquired about intraday tips',NULL,NULL),(12,'e0ca9224-a20f-49b9-9682-e850778f1f8a',NULL,'Suresh Iyer','9811001112','suresh.iyer@example.com',NULL,'Maharashtra','Nagpur',3,7,0,0,4,'2026-11-21 12:15:29',NULL,'2026-11-10 12:15:29','2026-11-21 12:15:29','Trading budget too small',NULL,NULL),(13,'56f6ef20-e2d7-4f36-8d2d-6b6ad0e56217',NULL,'Aditya Singhal','9811001113','aditya.singhal@example.com',NULL,'Uttar Pradesh','Noida',6,5,0,0,1,'2026-11-21 12:28:51',NULL,'2026-11-09 12:28:51','2026-11-21 12:28:51','Corporate treasury manager seeking institutional advisory rate card',NULL,NULL),(14,'73dee74b-79c6-47b6-87b4-968b7fec8560',NULL,'Bhavna Shah','9811001114','bhavna.shah@example.com',NULL,'Gujarat','Surat',5,3,0,0,2,'2026-11-21 12:28:51',NULL,'2026-11-08 12:28:51','2026-11-21 12:28:51','Interested in commodity options, promised payment confirmation by Friday',NULL,NULL),(15,'0fc3482f-ec0a-4305-9cbc-292968fe923f',NULL,'Gaurav Kapoor','9811001115','gaurav.k@example.com',NULL,'Haryana','Gurgaon',1,2,0,0,3,'2026-11-21 12:28:51',NULL,'2026-11-21 12:28:51','2026-11-21 12:28:51','Wants demo of real-time signals dashboard before making payment',NULL,NULL),(16,'e993ecc2-0f44-448f-8c29-a7ad88d8403b',NULL,'Meera Nambiar','9811001116','meera.n@example.com',NULL,'Kerala','Thiruvananthapuram',3,1,0,0,4,'2026-11-21 12:28:51',NULL,'2026-11-20 12:28:51','2026-11-21 12:28:51','Downloaded market trends whitepaper, waiting for initial callback',NULL,NULL),(17,'4ee92d23-43a6-41ca-bcda-b99da8fb3daf',NULL,'Naveen Chawla','9811001117','naveen.c@example.com',NULL,'Madhya Pradesh','Indore',2,6,0,0,5,'2026-11-21 12:28:51',NULL,'2026-11-19 12:28:51','2026-11-21 12:28:51','Opted for Options & Futures plan. Invoice paid via NetBanking.',NULL,NULL),(18,'109d39cc-d662-4fcf-8905-a1f8daaf0d5e',NULL,'Tarun Aggarwal','9811001118','tarun.a@example.com',NULL,'Punjab','Ludhiana',4,8,0,0,6,'2026-11-21 12:28:51',NULL,'2026-11-18 12:28:51','2026-11-21 12:28:51','Opted for discount broker self-trade package',NULL,NULL),(19,'LEADF435FA5F8634BC5C',4,'Aarav Sharma','9820111001','aarav.sharma@nortrade.example',NULL,NULL,NULL,2,NULL,0,0,NULL,NULL,'1','2026-11-21 12:47:32','2026-11-21 12:47:32','',NULL,NULL),(20,'LEADE70DA933E64C0537',4,'Diya Patel','9820111002','diya.patel@vertexbuild.example',NULL,NULL,NULL,2,NULL,0,0,NULL,NULL,'1','2026-11-21 12:47:32','2026-11-21 12:47:32','',NULL,NULL),(21,'LEAD6B1711E09C02C29A',4,'Rohan Verma','9820111003','rohan.verma@skylinearch.example',NULL,NULL,NULL,2,NULL,0,0,NULL,NULL,'1','2026-11-21 12:47:32','2026-11-21 12:47:32','',NULL,NULL),(22,'LEADAB8A075AFCB94D8D',4,'Ananya Iyer','9820111004','ananya.iyer@studioiyer.example',NULL,NULL,NULL,2,NULL,0,0,NULL,NULL,'1','2026-11-21 12:47:32','2026-11-21 12:47:32','',NULL,NULL),(23,'LEADBA1D874F658FBE99',4,'Vikramaditya Rao','9820111005','vikram.rao@raodesign.example',NULL,NULL,NULL,2,NULL,0,0,NULL,NULL,'1','2026-11-21 12:47:32','2026-11-21 12:47:32','',NULL,NULL),(24,'LEADACB9C287BCCB6925',4,'Meera Krishnan','9820111006','meera.k@krishnanassociates.example',NULL,NULL,NULL,2,NULL,0,0,NULL,NULL,'1','2026-11-21 12:47:32','2026-11-21 12:47:32','',NULL,NULL),(25,'LEAD6B614CE47F1F8539',4,'Kabir Malhotra','9820111007','kabir.m@malhotradev.example',NULL,NULL,NULL,2,NULL,0,0,NULL,NULL,'1','2026-11-21 12:47:32','2026-11-21 12:47:32','',NULL,NULL),(26,'LEAD15513B4ACF1187D0',4,'Ishita Joshi','9820111008','ishita.joshi@joshiplanners.example',NULL,NULL,NULL,2,NULL,0,0,NULL,NULL,'1','2026-11-21 12:47:32','2026-11-21 12:47:32','',NULL,NULL),(27,'LEAD1F78168DCBE79091',4,'Siddharth Menon','9820111009','siddharth.menon@menoninfra.example',NULL,NULL,NULL,2,NULL,0,0,NULL,NULL,'1','2026-11-21 12:47:32','2026-11-21 12:47:32','',NULL,NULL),(28,'LEAD90667CC1923B19F1',4,'Kavya Nair','9820111010','kavya.nair@atelierkavya.example',NULL,NULL,NULL,2,NULL,0,0,NULL,NULL,'1','2026-11-21 12:47:32','2026-11-21 12:47:32','',NULL,NULL),(29,'LEAD3CE55B5AF70E707B',4,'Arjun Kapoor','9820111011','arjun.kapoor@kapoorconstructions.example',NULL,NULL,NULL,2,NULL,0,0,NULL,NULL,'1','2026-11-21 12:47:32','2026-11-21 12:47:32','',NULL,NULL),(30,'LEADFE916F2D426C0C2B',4,'Nandini Kulkarni','9820111012','nandini.k@kulkarnistudio.example',NULL,NULL,NULL,2,NULL,0,0,NULL,NULL,'1','2026-11-21 12:47:32','2026-11-21 12:47:32','',NULL,NULL),(31,'LEAD5BF7EB8331EA400F',4,'Pranav Desai','9820111013','pranav.desai@desaibuilders.example',NULL,NULL,NULL,2,NULL,0,0,NULL,NULL,'1','2026-11-21 12:47:32','2026-11-21 12:47:32','',NULL,NULL),(32,'LEAD8205CA9F2C0A9F54',4,'Tara Chatterjee','9820111014','tara.c@chatterjeearch.example',NULL,NULL,NULL,2,NULL,0,0,NULL,NULL,'1','2026-11-21 12:47:32','2026-11-21 12:47:32','',NULL,NULL),(33,'LEADC49C528C0A509EE7',4,'Rishabh Gupta','9820111015','rishabh.gupta@guptarealty.example',NULL,NULL,NULL,2,NULL,0,0,NULL,NULL,'1','2026-11-21 12:47:32','2026-11-21 12:47:32','',NULL,NULL),(34,'LEAD8AA24DC3E8D66A7B',4,'Pooja Hegde','9820111016','pooja.hegde@hegdespaces.example',NULL,NULL,NULL,2,NULL,0,0,NULL,NULL,'1','2026-11-21 12:47:32','2026-11-21 12:47:32','',NULL,NULL),(35,'LEAD75682BEC0A2549CD',4,'Aditya Bansal','9820111017','aditya.bansal@bansalgroup.example',NULL,NULL,NULL,2,NULL,0,0,NULL,NULL,'1','2026-11-21 12:47:32','2026-11-21 12:47:32','',NULL,NULL),(36,'LEADEEE78959F1448264',4,'Sneha Choudhury','9820111018','sneha.c@choudhurydesign.example',NULL,NULL,NULL,2,NULL,0,0,NULL,NULL,'1','2026-11-21 12:47:32','2026-11-21 12:47:32','',NULL,NULL),(37,'LEADABC0EB0AE6D61538',4,'Karanbir Gill','9820111019','karanbir.gill@gillinfra.example',NULL,NULL,NULL,2,NULL,0,0,NULL,NULL,'1','2026-11-21 12:47:32','2026-11-21 12:47:32','',NULL,NULL),(38,'LEADBF2849055A7D14D4',4,'Shruti Agarwal','9820111020','shruti.agarwal@agarwalarch.example',NULL,NULL,NULL,2,NULL,0,0,NULL,NULL,'1','2026-11-21 12:47:32','2026-11-21 12:47:32','',NULL,NULL),(39,'LEADA953A39EAA9C7D75',4,'Nikhil Tiwari','9820111021','nikhil.tiwari@tiwariprojects.example',NULL,NULL,NULL,2,NULL,0,0,NULL,NULL,'1','2026-11-21 12:47:32','2026-11-21 12:47:32','',NULL,NULL),(40,'LEAD7BECF8E83B2078D1',4,'Ritika Sen','9820111022','ritika.sen@seninteriors.example',NULL,NULL,NULL,2,NULL,0,0,NULL,NULL,'1','2026-11-21 12:47:32','2026-11-21 12:47:32','',NULL,NULL),(41,'LEAD678EA9222930CA85',4,'Varun Mishra','9820111023','varun.mishra@mishradevelopers.example',NULL,NULL,NULL,2,NULL,1,0,NULL,NULL,'1','2026-11-21 12:47:32','2026-11-21 12:48:03','',NULL,NULL),(42,'LEADB873D3D6D2949E28',4,'Aishwarya Pillai','9820111024','aishwarya.p@pillaistudio.example',NULL,NULL,NULL,2,NULL,0,0,NULL,NULL,'1','2026-11-21 12:47:32','2026-11-21 12:47:32','',NULL,NULL),(43,'LEADF9FE9192458A33D8',4,'Harshvardhan Singh','9820111025','harsh.singh@singhheritage.example',NULL,NULL,NULL,2,NULL,0,0,NULL,NULL,'1','2026-11-21 12:47:32','2026-11-21 12:47:32','',NULL,NULL),(44,'LEAD55947ACBA8BC803A',4,'Divya Shetty','9820111026','divya.shetty@shettybuildtech.example',NULL,NULL,NULL,2,NULL,0,0,NULL,NULL,'1','2026-11-21 12:47:32','2026-11-21 12:47:32','',NULL,NULL),(45,'LEAD0C445BEA368820BD',4,'Manish Pandey','9820111027','manish.pandey@pandeyestates.example',NULL,NULL,NULL,2,NULL,0,0,NULL,NULL,'1','2026-11-21 12:47:32','2026-11-21 12:47:32','',NULL,NULL),(46,'LEAD55BB71F5335A5863',4,'Preeti Saxena','9820111028','preeti.saxena@saxenadesign.example',NULL,NULL,NULL,2,NULL,0,0,NULL,NULL,'1','2026-11-21 12:47:32','2026-11-21 12:47:32','',NULL,NULL),(47,'LEAD036EA7BB77800E75',4,'Yashwanth Reddy','9820111029','yash.reddy@reddyinfra.example',NULL,NULL,NULL,2,NULL,0,0,NULL,NULL,'1','2026-11-21 12:47:32','2026-11-21 12:47:32','',NULL,NULL),(48,'LEADF6CAB82902507DB7',4,'Komal Thakur','9820111030','komal.thakur@thakurspaces.example',NULL,NULL,NULL,2,NULL,0,0,NULL,NULL,'1','2026-11-21 12:47:32','2026-11-21 12:47:32','',NULL,NULL),(49,'LEAD595899EA38897AC4',4,'Raghavendra Bhat','9820111031','raghav.bhat@bhatarchitects.example',NULL,NULL,NULL,2,NULL,1,0,NULL,NULL,'1','2026-11-21 12:47:32','2026-11-21 12:48:01','',NULL,NULL),(50,'LEADDEDDDDB5EEC13301',4,'Simran Kaur','9820111032','simran.kaur@kaurdevelopments.example',NULL,NULL,NULL,2,NULL,0,0,NULL,NULL,'1','2026-11-21 12:47:32','2026-11-21 12:47:32','',NULL,NULL),(51,'LEAD681C774419949D55',4,'Abhishek Dubey','9820111033','abhishek.dubey@dubeyarch.example',NULL,NULL,NULL,2,NULL,0,0,NULL,NULL,'1','2026-11-21 12:47:32','2026-11-21 12:47:32','',NULL,NULL),(52,'LEAD6D6126C8121F6B28',4,'Gayatri Menon','9820111034','gayatri.menon@menonstudio.example',NULL,NULL,NULL,2,NULL,0,0,NULL,NULL,'1','2026-11-21 12:47:32','2026-11-21 12:47:32','',NULL,NULL),(53,'LEADC47DE4D1C4F0723A',4,'Sandeep Yadav','9820111035','sandeep.yadav@yadavrealty.example',NULL,NULL,NULL,2,NULL,0,0,NULL,NULL,'1','2026-11-21 12:47:32','2026-11-21 12:47:32','',NULL,NULL),(54,'LEAD46CED559C8E9AF46',4,'Ankita Mukherjee','9820111036','ankita.m@mukherjeeassociates.example',NULL,NULL,NULL,2,NULL,0,0,NULL,NULL,'1','2026-11-21 12:47:32','2026-11-21 12:47:32','',NULL,NULL),(55,'LEAD0121CFD4AABEB253',4,'Gaurav Chawla','9820111037','gaurav.chawla@chawlabuilders.example',NULL,NULL,NULL,2,NULL,0,0,NULL,NULL,'1','2026-11-21 12:47:32','2026-11-21 12:47:32','',NULL,NULL),(56,'LEADF89811CB4293E2A8',4,'Pallavi Deshmukh','9820111038','pallavi.d@deshmukharch.example',NULL,NULL,NULL,2,NULL,0,0,NULL,NULL,'1','2026-11-21 12:47:32','2026-11-21 12:47:32','',NULL,NULL),(57,'LEADA49003BBABF3A72D',4,'Tushar Kulkarni','9820111039','tushar.k@kulkarnigroup.example',NULL,NULL,NULL,2,NULL,1,0,NULL,NULL,'1','2026-11-21 12:47:32','2026-11-21 12:48:04','',NULL,NULL),(58,'LEAD930295536E006DAA',4,'Neha Gokhale','9820111040','neha.gokhale@gokhaledesign.example',NULL,NULL,NULL,2,NULL,0,0,NULL,NULL,'1','2026-11-21 12:47:32','2026-11-21 12:47:32','',NULL,NULL),(59,'LEADEB1A92D8D75FBBCC',4,'Rohan Joshi','9820111041','rohan.joshi@joshirealty.example',NULL,NULL,NULL,2,NULL,0,0,NULL,NULL,'1','2026-11-21 12:47:32','2026-11-21 12:47:32','',NULL,NULL),(60,'LEAD237A0B92BCB36248',4,'Shraddha Patil','9820111042','shraddha.patil@patilarchitects.example',NULL,NULL,NULL,2,NULL,0,0,NULL,NULL,'1','2026-11-21 12:47:32','2026-11-21 12:47:32','',NULL,NULL),(61,'LEADE976BFAE227E5A9A',4,'Vivek Sharma','9820111043','vivek.sharma@sharma',NULL,NULL,NULL,2,2,1,0,NULL,NULL,'1','2026-11-21 12:47:32','2026-11-21 12:49:41','No comment',NULL,NULL);
/*!40000 ALTER TABLE `leads` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `products`
--

DROP TABLE IF EXISTS `products`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `products` (
  `id` int NOT NULL AUTO_INCREMENT,
  `product_uuid` varchar(50) COLLATE utf8mb4_general_ci NOT NULL,
  `product_name` varchar(150) COLLATE utf8mb4_general_ci NOT NULL,
  `description` text COLLATE utf8mb4_general_ci,
  `status` tinyint(1) NOT NULL DEFAULT '1',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `weekly` decimal(10,2) DEFAULT '0.00',
  `two_weekly` decimal(10,2) DEFAULT '0.00',
  `monthly` decimal(10,2) DEFAULT '0.00',
  `two_monthly` decimal(10,2) DEFAULT '0.00',
  `quarterly` decimal(10,2) DEFAULT '0.00',
  `six_monthly` decimal(10,2) DEFAULT '0.00',
  `nine_monthly` decimal(10,2) DEFAULT '0.00',
  `yearly` decimal(10,2) DEFAULT '0.00',
  `eighteen_monthly` decimal(10,2) DEFAULT '0.00',
  `twenty_four_monthly` decimal(10,2) DEFAULT '0.00',
  PRIMARY KEY (`id`),
  UNIQUE KEY `product_uuid` (`product_uuid`)
) ENGINE=InnoDB AUTO_INCREMENT=8 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `products`
--

LOCK TABLES `products` WRITE;
/*!40000 ALTER TABLE `products` DISABLE KEYS */;
INSERT INTO `products` VALUES (1,'6c1dd42f-f3b6-48fa-9edd-a870691280c3','Equity Pro Advisory','Comprehensive intraday & swing advisory',1,'2026-11-21 12:15:29','2026-11-21 12:15:29',0.00,0.00,12000.00,0.00,28000.00,0.00,0.00,95000.00,0.00,0.00),(2,'82d805c9-0102-4231-a62c-a0e57403a8de','Options & Derivatives Strategy','Nifty & Bank Nifty hedging strategies',1,'2026-11-21 12:15:29','2026-11-21 12:15:29',0.00,0.00,16000.00,0.00,39000.00,0.00,0.00,135000.00,0.00,0.00),(3,'00f0fa28-348e-443b-a79a-fae5d4b41d98','Commodity Bullion Pack','Gold & Silver bullion trade setups',1,'2026-11-21 12:15:29','2026-11-21 12:15:29',0.00,0.00,14000.00,0.00,34000.00,0.00,0.00,115000.00,0.00,0.00),(4,'84bf3f8f-bcd3-49d9-aca2-f627d6973f1d','HNI Wealth Advisory','Customized high net-worth advisory',1,'2026-11-21 12:15:29','2026-11-21 12:15:29',0.00,0.00,35000.00,0.00,95000.00,0.00,0.00,320000.00,0.00,0.00),(5,'44202994-06a9-44be-a102-2817dbdbaa9e','Equity Premium Advisory','High conviction intraday and swing stock recommendations with precise risk:reward.',1,'2026-11-21 12:28:51','2026-11-21 12:28:51',0.00,0.00,15000.00,0.00,38000.00,0.00,0.00,120000.00,0.00,0.00),(6,'cbb35184-5f74-4397-9d9f-59cc600d3b5b','HNI Wealth Portfolio','Bespoke high net-worth asset allocation, multi-asset advisory and direct fund tracking.',1,'2026-11-21 12:28:51','2026-11-21 12:28:51',0.00,0.00,45000.00,0.00,115000.00,0.00,0.00,380000.00,0.00,0.00),(7,'64076af2-9225-49c9-97ee-a1d8f526ef61','Future Growth Advisory','Mid-cap and small-cap alpha discovery portfolio for medium-to-long term wealth creation.',1,'2026-11-21 12:28:51','2026-11-21 12:28:51',0.00,0.00,16000.00,0.00,39000.00,0.00,0.00,130000.00,0.00,0.00);
/*!40000 ALTER TABLE `products` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `recommendation`
--

DROP TABLE IF EXISTS `recommendation`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `recommendation` (
  `id` int NOT NULL AUTO_INCREMENT,
  `parent_id` int DEFAULT '0',
  `remote_id` int DEFAULT NULL,
  `segment` longtext COLLATE utf8mb4_general_ci NOT NULL,
  `recommendation` longtext COLLATE utf8mb4_general_ci NOT NULL,
  `recommendation_time` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `flag` enum('0','1') COLLATE utf8mb4_general_ci NOT NULL DEFAULT '0',
  `rational_done` int DEFAULT '0',
  `crm` varchar(255) COLLATE utf8mb4_general_ci DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `recommendation`
--

LOCK TABLES `recommendation` WRITE;
/*!40000 ALTER TABLE `recommendation` DISABLE KEYS */;
/*!40000 ALTER TABLE `recommendation` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `roles`
--

DROP TABLE IF EXISTS `roles`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `roles` (
  `id` int NOT NULL AUTO_INCREMENT,
  `role_uuid` varchar(40) COLLATE utf8mb4_general_ci NOT NULL,
  `role_name` varchar(100) COLLATE utf8mb4_general_ci NOT NULL,
  `permissions` longtext COLLATE utf8mb4_general_ci,
  `status` tinyint(1) NOT NULL DEFAULT '1',
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `lead_limit_per_user` int NOT NULL DEFAULT '10',
  PRIMARY KEY (`id`),
  UNIQUE KEY `role_uuid` (`role_uuid`)
) ENGINE=InnoDB AUTO_INCREMENT=5 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `roles`
--

LOCK TABLES `roles` WRITE;
/*!40000 ALTER TABLE `roles` DISABLE KEYS */;
INSERT INTO `roles` VALUES (1,'98e1b927-eb5b-425a-b3b7-6a0cfb37b74b','Administrator','{\"all\": true}',1,'2026-11-21 06:38:36','2026-11-21 06:38:36',10),(2,'bf61bf74-884b-4dbb-82b2-ce13457b7755','Sales Manager','{\"leads\": [\"view\", \"add\", \"edit\", \"export\", \"transfer\"], \"reports\": [\"view\"], \"operations\": [\"view\"]}',1,'2026-11-21 06:45:29','2026-11-21 06:45:29',10),(3,'40b1409d-73d3-46d1-986d-cf17abe5c0c5','Sales Executive','{\"leads\": [\"view\", \"add\", \"edit\"], \"followups\": [\"view\"], \"clients\": [\"view\"]}',1,'2026-11-21 06:45:29','2026-11-21 06:45:29',10),(4,'d8d52bc5-d947-4aaf-b93f-25e2e2b93fe7','Support Representative','{\"leads\": [\"view\"], \"clients\": [\"view\"]}',1,'2026-11-21 06:58:51','2026-11-21 06:58:51',10);
/*!40000 ALTER TABLE `roles` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `sales_orders`
--

DROP TABLE IF EXISTS `sales_orders`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `sales_orders` (
  `id` int NOT NULL AUTO_INCREMENT,
  `sales_order_uuid` varchar(40) COLLATE utf8mb4_general_ci NOT NULL,
  `lead_id` int NOT NULL,
  `created_by_user_id` int NOT NULL,
  `order_number` varchar(60) COLLATE utf8mb4_general_ci NOT NULL,
  `order_amount` decimal(12,2) NOT NULL DEFAULT '0.00',
  `order_status` enum('pending','approved','rejected','cancelled') COLLATE utf8mb4_general_ci NOT NULL DEFAULT 'pending',
  `notes` text COLLATE utf8mb4_general_ci,
  `approved_by_user_id` int DEFAULT NULL,
  `approved_at` datetime DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `invoice_name` varchar(160) COLLATE utf8mb4_general_ci DEFAULT NULL,
  `email` varchar(160) COLLATE utf8mb4_general_ci DEFAULT NULL,
  `address` text COLLATE utf8mb4_general_ci,
  `state` varchar(100) COLLATE utf8mb4_general_ci DEFAULT NULL,
  `city` varchar(100) COLLATE utf8mb4_general_ci DEFAULT NULL,
  `gst_number` varchar(30) COLLATE utf8mb4_general_ci DEFAULT NULL,
  `product_name` varchar(160) COLLATE utf8mb4_general_ci DEFAULT NULL,
  `plan_name` varchar(60) COLLATE utf8mb4_general_ci DEFAULT NULL,
  `gross_amount` decimal(12,2) DEFAULT '0.00',
  `tax_percentage` decimal(5,2) DEFAULT '0.00',
  `tax_amount` decimal(12,2) DEFAULT '0.00',
  `net_amount` decimal(12,2) DEFAULT '0.00',
  `service_start_date` date DEFAULT NULL,
  `service_expiry_date` date DEFAULT NULL,
  `payment_mode` varchar(60) COLLATE utf8mb4_general_ci DEFAULT NULL,
  `payment_date` date DEFAULT NULL,
  `reference_number` varchar(100) COLLATE utf8mb4_general_ci DEFAULT NULL,
  `pan_number` varchar(20) COLLATE utf8mb4_general_ci DEFAULT NULL,
  `aadhaar_number` varchar(20) COLLATE utf8mb4_general_ci DEFAULT NULL,
  `dob` date DEFAULT NULL,
  `service_mode` varchar(50) COLLATE utf8mb4_general_ci DEFAULT NULL,
  `kyc_status` varchar(50) COLLATE utf8mb4_general_ci DEFAULT 'Pending',
  `email_sent` tinyint(1) DEFAULT '0',
  `created_by_name` varchar(255) COLLATE utf8mb4_general_ci DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_sales_orders_uuid` (`sales_order_uuid`),
  UNIQUE KEY `uq_sales_orders_number` (`order_number`),
  KEY `idx_sales_orders_lead_id` (`lead_id`),
  KEY `idx_sales_orders_user_id` (`created_by_user_id`),
  KEY `idx_sales_orders_status` (`order_status`),
  KEY `fk_sales_orders_approved_user` (`approved_by_user_id`),
  CONSTRAINT `fk_sales_orders_approved_user` FOREIGN KEY (`approved_by_user_id`) REFERENCES `users` (`id`),
  CONSTRAINT `fk_sales_orders_created_user` FOREIGN KEY (`created_by_user_id`) REFERENCES `users` (`id`),
  CONSTRAINT `fk_sales_orders_lead` FOREIGN KEY (`lead_id`) REFERENCES `leads` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=29 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `sales_orders`
--

LOCK TABLES `sales_orders` WRITE;
/*!40000 ALTER TABLE `sales_orders` DISABLE KEYS */;
INSERT INTO `sales_orders` VALUES (1,'0724b783-5c06-4c88-8ce2-4254641668f6',6,1,'ORD-2026-001',18880.00,'approved','Client confirmed subscription',1,'2026-11-21 12:15:29','2026-11-21 00:00:00','2026-11-21 12:15:29','Manish Kulkarni',NULL,NULL,NULL,NULL,NULL,'Options & Derivatives Strategy','monthly',16000.00,18.00,2880.00,18880.00,'2026-11-21','2026-12-21','UPI','2026-11-21',NULL,NULL,NULL,NULL,NULL,'Pending',0,'System Administrator'),(2,'8c53932b-f23b-4f74-bef5-336cb63a95b2',7,1,'ORD-2026-002',112100.00,'approved','Client confirmed subscription',1,'2026-11-21 12:15:29','2026-11-19 00:00:00','2026-11-21 12:15:29','Pooja Singhania',NULL,NULL,NULL,NULL,NULL,'HNI Wealth Advisory','quarterly',95000.00,18.00,17100.00,112100.00,'2026-11-19','2026-12-19','Net Banking','2026-11-19',NULL,NULL,NULL,NULL,NULL,'Pending',0,'System Administrator'),(3,'be0c9ea4-563a-4b8b-a791-537728458a3f',10,1,'ORD-2026-003',33040.00,'approved','Client confirmed subscription',1,'2026-11-21 12:15:29','2026-11-17 00:00:00','2026-11-21 12:15:29','Deepak Bansal',NULL,NULL,NULL,NULL,NULL,'Equity Pro Advisory','quarterly',28000.00,18.00,5040.00,33040.00,'2026-11-17','2026-12-17','Credit Card','2026-11-17',NULL,NULL,NULL,NULL,NULL,'Pending',0,'System Administrator'),(4,'2c88e3ea-c92e-4657-b7a7-5753ca32addd',17,1,'ORD-2026-004',56640.00,'approved','Subscription package confirmed',1,'2026-11-21 12:28:51','2026-11-21 00:00:00','2026-11-21 12:28:51','Naveen Chawla',NULL,NULL,NULL,NULL,NULL,'Options & Derivatives Strategy','quarterly',48000.00,18.00,8640.00,56640.00,'2026-11-21','2027-02-19','Net Banking','2026-11-21',NULL,NULL,NULL,NULL,NULL,'Pending',0,'System Administrator'),(5,'54c52cf7-311e-4c77-9b71-91fa1bd7594c',5,1,'ORD-2026-005',153400.00,'pending','Subscription package confirmed',1,NULL,'2026-11-21 00:00:00','2026-11-21 12:28:51','Rohan Malhotra',NULL,NULL,NULL,NULL,NULL,'Future Growth Advisory','yearly',130000.00,18.00,23400.00,153400.00,'2026-11-21','2027-02-19','Cheque','2026-11-21',NULL,NULL,NULL,NULL,NULL,'Pending',0,'System Administrator'),(6,'1ef9ef4c-8039-403b-aa1a-dea9f5597eac',13,1,'ORD-2026-006',448400.00,'pending','Subscription package confirmed',1,NULL,'2026-11-19 00:00:00','2026-11-21 12:28:51','Aditya Singhal',NULL,NULL,NULL,NULL,NULL,'HNI Wealth Portfolio','yearly',380000.00,18.00,68400.00,448400.00,'2026-11-19','2027-02-17','Bank Transfer','2026-11-19',NULL,NULL,NULL,NULL,NULL,'Pending',0,'System Administrator'),(7,'eb825cbe-0f4a-44fd-a4c8-64e5c6012376',1,1,'ORD-2026-100',141600.00,'approved','High net-worth account. SEBI KYC verified.',1,'2026-11-21 12:31:21','2026-11-21 00:00:00','2026-11-21 12:31:21','Rajesh Mehta','rajesh.mehta@example.com','Suite 402, Trade Tower, Bandra Kurla Complex','Maharashtra','Mumbai',NULL,'Equity Premium Advisory','yearly',120000.00,18.00,21600.00,141600.00,'2026-11-21','2027-05-20','Net Banking','2026-11-21',NULL,NULL,NULL,NULL,NULL,'Pending',0,'System Administrator'),(8,'0a136ed4-e55f-4a51-abdb-faa9da32c361',2,2,'ORD-2026-101',56640.00,'approved','Active index options trader. Risk profiling score: 85/100.',1,'2026-11-21 12:31:21','2026-11-18 00:00:00','2026-11-21 12:31:21','Anita Desai','anita.desai@example.com','7th Floor, Koregaon Park Plaza','Maharashtra','Pune',NULL,'Options & Derivatives Strategy','quarterly',48000.00,18.00,8640.00,56640.00,'2026-11-18','2027-02-16','Net Banking','2026-11-18',NULL,NULL,NULL,NULL,NULL,'Pending',0,'System Administrator'),(9,'55c818ea-5e59-4279-ba5f-c20ab667bc10',3,3,'ORD-2026-102',21240.00,'approved','Focus on MCX Gold & Silver delivery signals.',1,'2026-11-21 12:31:21','2026-11-15 00:00:00','2026-11-21 12:31:21','Vikram Joshi','vikram.j@example.com','12/A 100ft Road, Indiranagar','Karnataka','Bangalore',NULL,'Commodity Bullion Pack','monthly',18000.00,18.00,3240.00,21240.00,'2026-11-15','2026-12-15','Net Banking','2026-11-15',NULL,NULL,NULL,NULL,NULL,'Pending',0,'System Administrator'),(10,'fe6549c9-aec6-4255-b377-58ab4c7314ac',4,4,'ORD-2026-103',88500.00,'approved','Corporate advisory account. Mandate signed.',1,'2026-11-21 12:31:21','2026-11-12 00:00:00','2026-11-21 12:31:21','Sunita Rao','sunita.rao@example.com','Plot 88, Financial District, Gachibowli','Telangana','Hyderabad',NULL,'Future Growth Advisory','six_monthly',75000.00,18.00,13500.00,88500.00,'2026-11-12','2027-05-11','Net Banking','2026-11-12',NULL,NULL,NULL,NULL,NULL,'Pending',0,'System Administrator'),(11,'21d9593a-df6d-4d49-999f-8fe74d10d843',5,1,'ORD-2026-104',448400.00,'approved','Multi-asset portfolio advisory with quarterly rebalancing.',1,'2026-11-21 12:31:21','2026-11-09 00:00:00','2026-11-21 12:31:21','Rohan Malhotra','rohan.m@example.com','B-14 Barakhamba Road, Connaught Place','Delhi','Delhi',NULL,'HNI Wealth Portfolio','yearly',380000.00,18.00,68400.00,448400.00,'2026-11-09','2027-11-09','Net Banking','2026-11-09',NULL,NULL,NULL,NULL,NULL,'Pending',0,'System Administrator'),(12,'23a76398-14d0-4095-9678-9acfae4ecfeb',6,2,'ORD-2026-105',23600.00,'approved','Intraday BankNifty strategy subscriber.',1,'2026-11-21 12:31:21','2026-11-06 00:00:00','2026-11-21 12:31:21','Manish Kulkarni','manish.k@example.com','Block C, Titanium City Centre, Satellite','Gujarat','Ahmedabad',NULL,'Options & Derivatives Strategy','monthly',20000.00,18.00,3600.00,23600.00,'2026-11-06','2026-12-06','Net Banking','2026-11-06',NULL,NULL,NULL,NULL,NULL,'Pending',0,'System Administrator'),(13,'019f561a-8295-458f-b531-70fe5c83e2d0',7,3,'ORD-2026-106',135700.00,'approved','Family office portfolio allocation client.',1,'2026-11-21 12:31:21','2026-11-03 00:00:00','2026-11-21 12:31:21','Pooja Singhania','pooja.s@example.com','Park Street Chambers, 3rd Floor','West Bengal','Kolkata',NULL,'HNI Wealth Portfolio','quarterly',115000.00,18.00,20700.00,135700.00,'2026-11-03','2027-02-01','Net Banking','2026-11-03',NULL,NULL,NULL,NULL,NULL,'Pending',0,'System Administrator'),(14,'b4f61307-830b-46f3-b68b-81eb9789d864',8,4,'ORD-2026-107',17700.00,'approved','Swing trading recommendations with SMS alerts.',1,'2026-11-21 12:31:21','2026-10-31 00:00:00','2026-11-21 12:31:21','Kavita Nair','kavita.nair@example.com','Marine Drive Towers, Ernakulam','Kerala','Kochi',NULL,'Equity Premium Advisory','monthly',15000.00,18.00,2700.00,17700.00,'2026-10-31','2026-11-30','Net Banking','2026-10-31',NULL,NULL,NULL,NULL,NULL,'Pending',0,'System Administrator'),(15,'c684e275-f3dc-4d36-b909-b33e8d21a14c',9,1,'ORD-2026-108',49560.00,'approved','Base metals & energy advisory pack.',1,'2026-11-21 12:31:21','2026-10-28 00:00:00','2026-11-21 12:31:21','Arjun Reddy','arjun.reddy@example.com','Anna Salai Business Hub, Mount Road','Tamil Nadu','Chennai',NULL,'Commodity Bullion Pack','quarterly',42000.00,18.00,7560.00,49560.00,'2026-10-28','2027-01-26','Net Banking','2026-10-28',NULL,NULL,NULL,NULL,NULL,'Pending',0,'System Administrator'),(16,'ac499869-8c9e-4546-aec0-389b6b5db095',10,2,'ORD-2026-109',44840.00,'approved','Equity delivery and positional swing calls.',1,'2026-11-21 12:31:21','2026-10-25 00:00:00','2026-11-21 12:31:21','Deepak Bansal','deepak.b@example.com','MI Road Commerce Complex','Rajasthan','Jaipur',NULL,'Equity Premium Advisory','quarterly',38000.00,18.00,6840.00,44840.00,'2026-10-25','2027-01-23','Net Banking','2026-10-25',NULL,NULL,NULL,NULL,NULL,'Pending',0,'System Administrator'),(17,'55e24cd8-d17d-405f-b032-fac92ff660a0',13,1,'ORD-2026-110',448400.00,'approved','Treasury funds advisory with monthly performance audit.',1,'2026-11-21 12:31:21','2026-10-22 00:00:00','2026-11-21 12:31:21','Aditya Singhal','aditya.singhal@example.com','Sector 62 Institutional Area','Uttar Pradesh','Noida',NULL,'HNI Wealth Portfolio','yearly',380000.00,18.00,68400.00,448400.00,'2026-10-22','2027-10-22','Net Banking','2026-10-22',NULL,NULL,NULL,NULL,NULL,'Pending',0,'System Administrator'),(18,'f600492c-8a84-43eb-aace-74e27e6969a8',14,2,'ORD-2026-111',46020.00,'approved','Midcap wealth compounder portfolio.',1,'2026-11-21 12:31:21','2026-10-19 00:00:00','2026-11-21 12:31:21','Bhavna Shah','bhavna.shah@example.com','Ring Road Diamond Market','Gujarat','Surat',NULL,'Future Growth Advisory','quarterly',39000.00,18.00,7020.00,46020.00,'2026-10-19','2027-01-17','Net Banking','2026-10-19',NULL,NULL,NULL,NULL,NULL,'Pending',0,'System Administrator'),(19,'75b86953-2b3b-4b1f-8f6d-5b56cb7b69bb',17,5,'ORD-2026-112',56640.00,'approved','Automated hedging recommendations.',1,'2026-11-21 12:31:21','2026-10-16 00:00:00','2026-11-21 12:31:21','Naveen Chawla','naveen.c@example.com','AB Road Tech Park','Madhya Pradesh','Indore',NULL,'Options & Derivatives Strategy','quarterly',48000.00,18.00,8640.00,56640.00,'2026-10-16','2027-01-14','Net Banking','2026-10-16',NULL,NULL,NULL,NULL,NULL,'Pending',0,'System Administrator'),(20,'921f3b6a-ed20-4de1-9847-7796d71f92fd',1,1,'ORD-2026-ADM1',448400.00,'approved','Monthly sales quota achievement deal',1,'2026-11-21 12:33:43','2026-11-19 00:00:00','2026-11-21 12:33:43','Client Invoice',NULL,NULL,NULL,NULL,NULL,'HNI Wealth Portfolio','yearly',380000.00,18.00,68400.00,448400.00,'2026-11-19','2027-02-17','Net Banking','2026-11-19',NULL,NULL,NULL,NULL,NULL,'Pending',0,'Team Lead'),(21,'91c93dd3-dd6d-438c-8904-1a3d782ab76a',2,2,'ORD-2026-RHL1',76700.00,'approved','Monthly sales quota achievement deal',1,'2026-11-21 12:33:43','2026-11-18 00:00:00','2026-11-21 12:33:43','Client Invoice',NULL,NULL,NULL,NULL,NULL,'Options & Derivatives Strategy','quarterly',65000.00,18.00,11700.00,76700.00,'2026-11-18','2027-02-16','Net Banking','2026-11-18',NULL,NULL,NULL,NULL,NULL,'Pending',0,'Team Lead'),(22,'ea476d85-b55b-4c56-a3c7-edefc3b1b331',3,2,'ORD-2026-RHL2',56640.00,'approved','Monthly sales quota achievement deal',1,'2026-11-21 12:33:43','2026-11-20 00:00:00','2026-11-21 12:33:43','Client Invoice',NULL,NULL,NULL,NULL,NULL,'Equity Premium Advisory','quarterly',48000.00,18.00,8640.00,56640.00,'2026-11-20','2027-02-18','Net Banking','2026-11-20',NULL,NULL,NULL,NULL,NULL,'Pending',0,'Team Lead'),(23,'6f25a18e-5b34-4697-aeb2-604e6e578266',4,3,'ORD-2026-PRY1',135700.00,'approved','Monthly sales quota achievement deal',1,'2026-11-21 12:33:43','2026-11-17 00:00:00','2026-11-21 12:33:43','Client Invoice',NULL,NULL,NULL,NULL,NULL,'HNI Wealth Portfolio','quarterly',115000.00,18.00,20700.00,135700.00,'2026-11-17','2027-02-15','Net Banking','2026-11-17',NULL,NULL,NULL,NULL,NULL,'Pending',0,'Team Lead'),(24,'fd5a6c61-a1fb-4ecd-bdf5-0370761d57cc',5,3,'ORD-2026-PRY2',25960.00,'approved','Monthly sales quota achievement deal',1,'2026-11-21 12:33:43','2026-11-20 00:00:00','2026-11-21 12:33:43','Client Invoice',NULL,NULL,NULL,NULL,NULL,'Commodity Bullion Pack','monthly',22000.00,18.00,3960.00,25960.00,'2026-11-20','2027-02-18','Net Banking','2026-11-20',NULL,NULL,NULL,NULL,NULL,'Pending',0,'Team Lead'),(25,'00ab5b5d-9c40-4a45-bc54-8e9a9f229afb',6,4,'ORD-2026-AMT1',88500.00,'approved','Monthly sales quota achievement deal',1,'2026-11-21 12:33:43','2026-11-19 00:00:00','2026-11-21 12:33:43','Client Invoice',NULL,NULL,NULL,NULL,NULL,'Future Growth Advisory','six_monthly',75000.00,18.00,13500.00,88500.00,'2026-11-19','2027-02-17','Net Banking','2026-11-19',NULL,NULL,NULL,NULL,NULL,'Pending',0,'Team Lead'),(26,'1f655cbf-30d9-4033-976c-4dba2a0fef31',7,4,'ORD-2026-AMT2',21240.00,'approved','Monthly sales quota achievement deal',1,'2026-11-21 12:33:43','2026-11-21 00:00:00','2026-11-21 12:33:43','Client Invoice',NULL,NULL,NULL,NULL,NULL,'Equity Premium Advisory','monthly',18000.00,18.00,3240.00,21240.00,'2026-11-21','2027-02-19','Net Banking','2026-11-21',NULL,NULL,NULL,NULL,NULL,'Pending',0,'Team Lead'),(27,'7f5e166e-ae24-4a73-84a1-90094293f716',8,5,'ORD-2026-SNH1',56640.00,'approved','Monthly sales quota achievement deal',1,'2026-11-21 12:33:43','2026-11-18 00:00:00','2026-11-21 12:33:43','Client Invoice',NULL,NULL,NULL,NULL,NULL,'Options & Derivatives Strategy','quarterly',48000.00,18.00,8640.00,56640.00,'2026-11-18','2027-02-16','Net Banking','2026-11-18',NULL,NULL,NULL,NULL,NULL,'Pending',0,'Team Lead'),(28,'7fcd1ffa-6bfc-4075-835d-0961d9e3cf1e',9,5,'ORD-2026-SNH2',23600.00,'approved','Monthly sales quota achievement deal',1,'2026-11-21 12:33:43','2026-11-21 00:00:00','2026-11-21 12:33:43','Client Invoice',NULL,NULL,NULL,NULL,NULL,'Commodity Bullion Pack','monthly',20000.00,18.00,3600.00,23600.00,'2026-11-21','2027-02-19','Net Banking','2026-11-21',NULL,NULL,NULL,NULL,NULL,'Pending',0,'Team Lead');
/*!40000 ALTER TABLE `sales_orders` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `service_settings`
--

DROP TABLE IF EXISTS `service_settings`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `service_settings` (
  `id` int NOT NULL AUTO_INCREMENT,
  `company_uid` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `company_name` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `crm_domain` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `ips_list` text COLLATE utf8mb4_unicode_ci,
  `plan_expiry_date` date DEFAULT NULL,
  `is_blocked` tinyint(1) DEFAULT '0',
  `notes` text COLLATE utf8mb4_unicode_ci,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uniq_company_uid` (`company_uid`)
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `service_settings`
--

LOCK TABLES `service_settings` WRITE;
/*!40000 ALTER TABLE `service_settings` DISABLE KEYS */;
INSERT INTO `service_settings` VALUES (1,'CMP-CAEFA18C12A2','Online CRM','localhost:5055','127.0.0.1, ::1, 0.0.0.0, 152.59.26.52','2099-12-31',0,NULL,'2026-11-21 12:08:36','2026-11-21 12:28:51');
/*!40000 ALTER TABLE `service_settings` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `system_settings`
--

DROP TABLE IF EXISTS `system_settings`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `system_settings` (
  `id` int NOT NULL AUTO_INCREMENT,
  `setting_key` varchar(100) COLLATE utf8mb4_general_ci NOT NULL,
  `setting_value` text COLLATE utf8mb4_general_ci,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `setting_key` (`setting_key`)
) ENGINE=InnoDB AUTO_INCREMENT=33 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `system_settings`
--

LOCK TABLES `system_settings` WRITE;
/*!40000 ALTER TABLE `system_settings` DISABLE KEYS */;
INSERT INTO `system_settings` VALUES (1,'sales_display_with_gst','1','2026-11-21 12:15:29'),(2,'company_brand_name','Apex Wealth CRM','2026-11-21 12:28:51'),(3,'company_brand_sales_gst','18.0','2026-11-21 12:15:29'),(4,'company_brand_tax','GSTIN: 27AABCA1234F1Z5','2026-11-21 12:15:29'),(5,'default_currency','INR','2026-11-21 12:15:29'),(11,'enable_birthday_alert','1','2026-11-21 12:28:51'),(12,'enable_so_approved_alert','1','2026-11-21 12:28:51'),(13,'enable_daily_reminder','1','2026-11-21 12:28:51'),(14,'dashboard_chart_designations','6,1,2,3','2026-11-21 12:33:43');
/*!40000 ALTER TABLE `system_settings` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `user_activities`
--

DROP TABLE IF EXISTS `user_activities`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `user_activities` (
  `id` int NOT NULL AUTO_INCREMENT,
  `user_activity_uuid` varchar(50) COLLATE utf8mb4_general_ci NOT NULL,
  `user_id` int DEFAULT NULL,
  `lead_id` int DEFAULT NULL,
  `action_type` varchar(100) COLLATE utf8mb4_general_ci NOT NULL,
  `description` text COLLATE utf8mb4_general_ci,
  `ip_address` varchar(45) COLLATE utf8mb4_general_ci DEFAULT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `user_activity_uuid` (`user_activity_uuid`)
) ENGINE=InnoDB AUTO_INCREMENT=28 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `user_activities`
--

LOCK TABLES `user_activities` WRITE;
/*!40000 ALTER TABLE `user_activities` DISABLE KEYS */;
INSERT INTO `user_activities` VALUES (1,'UACT72BF33595B1D',1,NULL,'User Login','User \'admin\' logged in successfully','152.59.26.52','2026-11-21 12:10:13'),(2,'UACTE42D5DD844DA',1,NULL,'User Login','User \'admin\' logged in successfully','152.59.26.52','2026-11-21 12:10:17'),(3,'UACTD48AD2BBE268',1,NULL,'User Login','User \'admin\' logged in successfully','152.59.26.52','2026-11-21 12:10:38'),(4,'UACTCCA41BAA59D9',1,NULL,'User Login','User \'admin\' logged in successfully','152.59.26.52','2026-11-21 12:12:30'),(5,'UACT75299B6B2929',1,NULL,'User Login','User \'admin\' logged in successfully','152.59.26.52','2026-11-21 12:15:34'),(6,'UACT977EAE8A6E3F',1,NULL,'User Login','User \'admin\' logged in successfully','152.59.26.52','2026-11-21 12:15:44'),(7,'UACTE98EF44508F3',1,NULL,'User Login','User \'admin\' logged in successfully','152.59.26.52','2026-11-21 12:21:38'),(8,'UACTB39DBE3778DF',1,NULL,'User Login','User \'admin\' logged in successfully','152.59.26.52','2026-11-21 12:22:35'),(9,'UACT9040BB1D78DA',1,NULL,'User Login','User \'admin\' logged in successfully','152.59.26.52','2026-11-21 12:26:45'),(10,'UACTF4973642E5DE',1,NULL,'User Login','User \'admin\' logged in successfully','152.59.26.52','2026-11-21 12:28:58'),(11,'UACTF1B37D37C061',1,NULL,'User Login','User \'admin\' logged in successfully','152.59.26.52','2026-11-21 12:29:12'),(12,'UACT7CCE37F7AD75',1,NULL,'User Login','User \'admin\' logged in successfully','152.59.26.52','2026-11-21 12:29:16'),(13,'UACTD2C79D20DB2C',1,NULL,'User Login','User \'admin\' logged in successfully','152.59.26.52','2026-11-21 12:29:24'),(14,'UACT3F2CC7BF86C0',1,NULL,'User Login','User \'admin\' logged in successfully','152.59.26.52','2026-11-21 12:30:12'),(15,'UACT7CC5DC792D49',1,NULL,'User Login','User \'admin\' logged in successfully','152.59.26.52','2026-11-21 12:31:25'),(16,'UACT40312EEDC702',1,NULL,'User Login','User \'admin\' logged in successfully','152.59.26.52','2026-11-21 12:31:31'),(17,'UACT0674053328A2',1,NULL,'User Login','User \'admin\' logged in successfully','152.59.26.52','2026-11-21 12:32:52'),(18,'UACT27774C26F5CB',1,NULL,'User Login','User \'admin\' logged in successfully','152.59.26.52','2026-11-21 12:33:49'),(19,'UACT100B2AC552ED',1,NULL,'User Login','User \'admin\' logged in successfully','152.59.26.52','2026-11-21 12:33:56'),(20,'UACT9F224F266B78',1,NULL,'User Login','User \'admin\' logged in successfully','152.59.26.52','2026-11-21 12:36:17'),(21,'UACT0DC390F4522F',1,61,'Click to Call','Initiated click-to-call to lead 61 (Vivek Sharma)','127.0.0.1','2026-11-21 12:47:50'),(22,'UACT16FCF1A7E829',1,61,'Click to Call','Initiated click-to-call to lead 61 (Vivek Sharma)','127.0.0.1','2026-11-21 12:47:58'),(23,'UACT814313429039',1,61,'Click to Call','Initiated click-to-call to lead 61 (Vivek Sharma)','127.0.0.1','2026-11-21 12:48:00'),(24,'UACT0D310BF0EE49',1,49,'Click to Call','Initiated click-to-call to lead 49 (Raghavendra Bhat)','127.0.0.1','2026-11-21 12:48:01'),(25,'UACTA97CCB1903B3',1,41,'Click to Call','Initiated click-to-call to lead 41 (Varun Mishra)','127.0.0.1','2026-11-21 12:48:03'),(26,'UACT33D3E993A63B',1,57,'Click to Call','Initiated click-to-call to lead 57 (Tushar Kulkarni)','127.0.0.1','2026-11-21 12:48:04'),(27,'UACTE4B3E17004BF',1,61,'Lead Response Saved','Updated status of lead 61 (Vivek Sharma) to \'Interested\'','127.0.0.1','2026-11-21 12:49:41');
/*!40000 ALTER TABLE `user_activities` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `user_sessions`
--

DROP TABLE IF EXISTS `user_sessions`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `user_sessions` (
  `id` int NOT NULL AUTO_INCREMENT,
  `session_token` varchar(128) COLLATE utf8mb4_general_ci NOT NULL,
  `user_id` int NOT NULL,
  `user_uuid` varchar(64) COLLATE utf8mb4_general_ci NOT NULL,
  `username` varchar(100) COLLATE utf8mb4_general_ci DEFAULT NULL,
  `ip_address` varchar(45) COLLATE utf8mb4_general_ci DEFAULT NULL,
  `user_agent` text COLLATE utf8mb4_general_ci,
  `is_active` tinyint(1) DEFAULT '1',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `last_activity` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `expires_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `session_token` (`session_token`),
  KEY `idx_user_uuid` (`user_uuid`),
  KEY `idx_session_token` (`session_token`),
  KEY `idx_is_active` (`is_active`)
) ENGINE=InnoDB AUTO_INCREMENT=21 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `user_sessions`
--

LOCK TABLES `user_sessions` WRITE;
/*!40000 ALTER TABLE `user_sessions` DISABLE KEYS */;
INSERT INTO `user_sessions` VALUES (1,'sess_4b4a6267ebe09c857cb180abbaa0891a5a934831fd84fb97',1,'fc5bacb0-3f65-4db0-8','admin','152.59.26.52','curl/8.7.1',1,'2026-11-21 12:10:13','2026-11-21 12:10:13','2026-12-21 12:10:13'),(2,'sess_5fe9cded1c7e14ce6c6fae9789880142f864e3bf5df7aa70',1,'fc5bacb0-3f65-4db0-8','admin','152.59.26.52','curl/8.7.1',1,'2026-11-21 12:10:17','2026-11-21 12:10:17','2026-12-21 12:10:17'),(3,'sess_0d536c4678b4fc537a5688c2ce30ed9820202b3b8f2f989e',1,'fc5bacb0-3f65-4db0-8','admin','152.59.26.52','Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/157.0.0.0 Safari/537.36',0,'2026-11-21 12:10:38','2026-11-22 11:37:17','2026-12-21 12:10:38'),(4,'sess_2c96c06257ac4d94567e6d579a9c855c8def5fdf33226f2d',1,'fc5bacb0-3f65-4db0-8','admin','152.59.26.52','curl/8.7.1',1,'2026-11-21 12:12:30','2026-11-21 12:12:30','2026-12-21 12:12:30'),(5,'sess_6d5cc4643c8a1f8c4ca12e4e27d2481435372e36b597efd0',1,'fc5bacb0-3f65-4db0-8','admin','152.59.26.52','curl/8.7.1',1,'2026-11-21 12:15:34','2026-11-21 12:15:34','2026-12-21 12:15:34'),(6,'sess_470fe158cf3e3ece73be067fdcd8874bbacbdbf48ead9b0b',1,'fc5bacb0-3f65-4db0-8','admin','152.59.26.52','curl/8.7.1',1,'2026-11-21 12:15:44','2026-11-21 12:15:44','2026-12-21 12:15:44'),(7,'sess_10fd2d47b8795ff1db651c916a36463d0bab3f0a9190718e',1,'fc5bacb0-3f65-4db0-8','admin','152.59.26.52','curl/8.7.1',1,'2026-11-21 12:21:38','2026-11-21 12:21:38','2026-12-21 12:21:38'),(8,'sess_940825538929e7ab9b3b3e3b1e4f183eba2eac814f91ada8',1,'fc5bacb0-3f65-4db0-8','admin','152.59.26.52','curl/8.7.1',1,'2026-11-21 12:22:35','2026-11-21 12:22:35','2026-12-21 12:22:35'),(9,'sess_c99f1df678a44c01f7ba05011edf2519f8a9f1ea15afcc24',1,'fc5bacb0-3f65-4db0-8','admin','152.59.26.52','curl/8.7.1',1,'2026-11-21 12:26:45','2026-11-21 12:26:45','2026-12-21 12:26:45'),(10,'sess_22bc53b43ff9759fda2dcf85894f42103f79532d07f7a6c4',1,'fc5bacb0-3f65-4db0-8','admin','152.59.26.52','curl/8.7.1',1,'2026-11-21 12:28:58','2026-11-21 12:28:58','2026-12-21 12:28:58'),(11,'sess_49ad9ead3b22847bdf29510a22220b4799bf63ccfb433a54',1,'fc5bacb0-3f65-4db0-8','admin','152.59.26.52','curl/8.7.1',1,'2026-11-21 12:29:13','2026-11-21 12:29:13','2026-12-21 12:29:13'),(12,'sess_149bccea22fd249347b476f73042e414da6d8868482f14e7',1,'fc5bacb0-3f65-4db0-8','admin','152.59.26.52','curl/8.7.1',1,'2026-11-21 12:29:16','2026-11-21 12:29:16','2026-12-21 12:29:16'),(13,'sess_1193dd1619f9d1e2f4254cbfa97a59de89d6a8a8f396a9de',1,'fc5bacb0-3f65-4db0-8','admin','152.59.26.52','curl/8.7.1',1,'2026-11-21 12:29:24','2026-11-21 12:29:24','2026-12-21 12:29:24'),(14,'sess_c33ffc6b5246c8c9a7e1e164fc360165527d1f3e7b8141ce',1,'fc5bacb0-3f65-4db0-8','admin','152.59.26.52','curl/8.7.1',1,'2026-11-21 12:30:12','2026-11-21 12:30:12','2026-12-21 12:30:12'),(15,'sess_57b04d1bd5ba0abf724e363cdffa6a334bf110ede8b33e61',1,'fc5bacb0-3f65-4db0-8','admin','152.59.26.52','curl/8.7.1',1,'2026-11-21 12:31:25','2026-11-21 12:31:25','2026-12-21 12:31:25'),(16,'sess_37c222620b8f6e7f0908128ca19305d9e3b65acde82a37e8',1,'fc5bacb0-3f65-4db0-8','admin','152.59.26.52','curl/8.7.1',1,'2026-11-21 12:31:31','2026-11-21 12:31:31','2026-12-21 12:31:31'),(17,'sess_8af9cea0e14330ec594f7fc7d1b424f0e097fe0e72138cb0',1,'fc5bacb0-3f65-4db0-8','admin','152.59.26.52','curl/8.7.1',1,'2026-11-21 12:32:52','2026-11-21 12:32:52','2026-12-21 12:32:52'),(18,'sess_8285950728c4df4c1324303772ee1017f0675aea7914a2c0',1,'fc5bacb0-3f65-4db0-8','admin','152.59.26.52','curl/8.7.1',1,'2026-11-21 12:33:49','2026-11-21 12:33:49','2026-12-21 12:33:49'),(19,'sess_6f3eb6169b86ff1cb8085998f43c8df2de3a15b660fb8501',1,'fc5bacb0-3f65-4db0-8','admin','152.59.26.52','curl/8.7.1',1,'2026-11-21 12:33:56','2026-11-21 12:33:56','2026-12-21 12:33:56'),(20,'sess_f4287757fce31de9823076e532f53f9d7d12a6742b01e4d1',1,'fc5bacb0-3f65-4db0-8','admin','152.59.26.52','curl/8.7.1',1,'2026-11-21 12:36:17','2026-11-21 12:36:17','2026-12-21 12:36:17');
/*!40000 ALTER TABLE `user_sessions` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `users`
--

DROP TABLE IF EXISTS `users`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `users` (
  `id` int NOT NULL AUTO_INCREMENT,
  `user_uuid` varchar(20) COLLATE utf8mb4_general_ci NOT NULL,
  `full_name` varchar(150) COLLATE utf8mb4_general_ci NOT NULL,
  `username` varchar(100) COLLATE utf8mb4_general_ci NOT NULL,
  `mobile` varchar(20) COLLATE utf8mb4_general_ci DEFAULT NULL,
  `password` varchar(255) COLLATE utf8mb4_general_ci NOT NULL,
  `extension_id` int DEFAULT NULL,
  `role_id` int DEFAULT NULL,
  `designation_id` int DEFAULT NULL,
  `date_of_birth` date DEFAULT NULL,
  `date_of_joining` date DEFAULT NULL,
  `biometric_id` int DEFAULT NULL,
  `reporting_to_user_id` int DEFAULT NULL,
  `target` int NOT NULL DEFAULT '0',
  `click_to_call` enum('0','1') COLLATE utf8mb4_general_ci NOT NULL DEFAULT '1',
  `number_show_hide` enum('0','1') COLLATE utf8mb4_general_ci NOT NULL DEFAULT '1',
  `status` tinyint NOT NULL DEFAULT '1',
  `updated_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `require_otp_for_login` tinyint(1) DEFAULT '0',
  `outside_login` tinyint(1) DEFAULT '0',
  `is_admin` tinyint(1) NOT NULL DEFAULT '0',
  `login_otp` varchar(10) COLLATE utf8mb4_general_ci DEFAULT NULL,
  `login_otp_created_at` datetime DEFAULT NULL,
  `last_active_at` datetime DEFAULT NULL,
  `live_status` varchar(20) COLLATE utf8mb4_general_ci DEFAULT 'offline',
  PRIMARY KEY (`id`),
  UNIQUE KEY `unique_user_uuid` (`user_uuid`)
) ENGINE=InnoDB AUTO_INCREMENT=8 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `users`
--

LOCK TABLES `users` WRITE;
/*!40000 ALTER TABLE `users` DISABLE KEYS */;
INSERT INTO `users` VALUES (1,'fc5bacb0-3f65-4db0-8','System Administrator','admin','9999999999','admin123',1,1,6,NULL,NULL,NULL,NULL,600000,'1','1',1,'2026-11-22 06:07:22','2026-11-21 06:38:36',0,1,1,'984595','2026-11-22 11:37:22','2026-11-22 11:37:14','online'),(2,'32bf977e-2523-4591-9','Rahul Sharma','rahul.sharma','9876543210','password123',2,2,1,'1990-05-14','2023-01-10',NULL,1,450000,'1','1',1,'2026-11-21 06:58:51','2026-11-21 06:45:29',0,1,0,NULL,NULL,NULL,'offline'),(3,'56a55b35-bd84-4cf4-8','Priya Patel','priya.patel','9876543211','password123',3,3,2,'1994-08-22','2023-06-15',NULL,1,300000,'1','1',1,'2026-11-21 06:58:51','2026-11-21 06:45:29',0,1,0,NULL,NULL,NULL,'offline'),(4,'6bb32a2c-a6e2-42b1-9','Amit Kumar','amit.kumar','9876543212','password123',4,3,3,'1995-11-03','2024-02-01',NULL,2,250000,'1','1',1,'2026-11-21 06:58:51','2026-11-21 06:45:29',0,1,0,NULL,NULL,NULL,'offline'),(5,'5bcc96b0-5af0-452b-9','Sneha Verma','sneha.verma','9876543213','password123',5,3,3,'1996-03-29','2024-03-10',NULL,2,250000,'1','1',1,'2026-11-21 06:58:51','2026-11-21 06:45:29',0,1,0,NULL,NULL,NULL,'offline'),(6,'2b2a937b-c859-43a4-b','Vikas Yadav','vikas.yadav','9876543214','password123',6,3,7,'1992-09-17','2023-09-01',NULL,2,350000,'1','1',1,'2026-11-21 06:58:51','2026-11-21 06:58:51',0,1,0,NULL,NULL,NULL,'offline'),(7,'4f060a0a-5997-44a5-b','Anjali Menon','anjali.menon','9876543215','password123',7,4,5,'1997-12-05','2024-05-20',NULL,1,100000,'1','1',1,'2026-11-21 06:58:51','2026-11-21 06:58:51',0,1,0,NULL,NULL,NULL,'offline');
/*!40000 ALTER TABLE `users` ENABLE KEYS */;
UNLOCK TABLES;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2026-11-22 11:51:19
