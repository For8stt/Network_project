local my_proto = Proto("my_proto", "Kisil")


local f_fragment_number = ProtoField.uint32("my_proto.fragment_number", "Fragment Number", base.DEC)
local f_last_fragment = ProtoField.uint8("my_proto.last_fragment", "Last Fragment", base.DEC, {[0] = "No", [1] = "Yes"})
local f_message_type = ProtoField.uint8("my_proto.message_type", "Message Type", base.DEC, {
    [0] = "Text",
    [1] = "File",
    [2] = "Handshake",
    [3] = "Name File",
    [4] = "ACK",
    [5] = "Heartbeat",
    [6] = "Heartbeat Reply",
    [7] = "NACK"
})
local f_crc = ProtoField.uint16("my_proto.crc", "CRC", base.HEX)


my_proto.fields = {f_fragment_number, f_last_fragment, f_message_type, f_crc}


local message_types = {
    [0] = "Text",
    [1] = "File",
    [2] = "Handshake",
    [3] = "Name File",
    [4] = "ACK",
    [5] = "Heartbeat",
    [6] = "Heartbeat Reply",
    [7] = "NACK"
}

function my_proto.dissector(buffer, pinfo, tree)
    if buffer:len() < 2 then
        return
    end

    pinfo.cols.protocol = "Kisil"

    local message_type = buffer(5, 1):uint()
    local message_type_str = message_types[message_type] or "Unknown"

    pinfo.cols.info:set("Message Type: " .. message_type_str)

    local subtree = tree:add(my_proto, buffer(), "My Protocol Data")
    subtree:add(f_fragment_number, buffer(0, 4)) 
    subtree:add(f_last_fragment, buffer(4, 1))   
    subtree:add(f_message_type, buffer(5, 1))    
    subtree:add(f_crc, buffer(6, 2))           
end

local udp_port = DissectorTable.get("udp.port")
udp_port:add(50601, my_proto)  
udp_port:add(50602, my_proto) 