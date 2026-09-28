#ID pattern works like this
#example id 311012
#The First number (here it is 3) is the game
#so 1 = ce, 2 = halo 2, 3 = halo 3, 4 = halo 4, 5 = ODST, 6 = Reach
#next 2 numbers (here 11) is the mission number
#here it would be mission 11, with the first number (3) we know the item has to do with mission 11 of halo 3
# the next 2 numbers (here 01) is the item/location type, here 01 means a chapter location, 00 would be level completion
#the last number (2) is to do with the item/location type. here it would mean the second chapter
#using this pattern we know this id is for the location of the 2nd chapter of the 11th mission of halo 3

#for misc items they are placed below id 100000 which is where this pattern starts, for instance skulls, which are for
#all games, are placed at 90000

#Misc offsets
SKULL_OFFSET = 90000

#ce game offset
CE_OFFSET = 100000

#ce missions offsets
PILLER_OF_AUTUMN_OFFSET = CE_OFFSET + 1000
HALO_CE_MISSION_OFFSET = CE_OFFSET + 2000
TRUTH_AND_RECONCILIATION_OFFSET = CE_OFFSET + 3000
SILENT_CARTOGRAPHER_OFFSET = CE_OFFSET + 4000
ASSAULT_CONTROL_ROOM_OFFSET = CE_OFFSET + 5000
GUILTY_SPARK_OFFSET = CE_OFFSET + 6000
LIBRARY_OFFSET = CE_OFFSET + 7000
TWO_BETRAYALS_OFFSET = CE_OFFSET + 8000
KEYS_OFFSET = CE_OFFSET + 9000
MAW_OFFSET = CE_OFFSET + 10000

#type offsets
CHAPTER_OFFSET = 10 # final number is the chapter number for the mission EX: the first chapter would be 11, second 12.
SKULL_LOCATION_OFFSET = 20 #final number 1, if more than 1 skull in mission then goes 1,2,3...

